from pathlib import Path
from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import json
import logging
import uuid

from game import Game
from player import Player
from params import *
from rules import *
from messages import MESSAGE_KEYS, build_message
from identity import createJoinCode, createPlayerId, createResumeToken, createSessionId, hashResumeToken, resumeTokenMatches
from versions import WEBSOCKET_PROTOCOL_VERSION
from persistent_state import SessionMetadataState
from clock import Clock, SYSTEM_CLOCK
from app_logging import configureApplicationLogging

configureApplicationLogging()
logger = logging.getLogger("toc.main")

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
CLIENT_MESSAGE_TYPES = frozenset({
	"configure-player",
	"debug",
	"text_input",
	"card_selection",
	"spot_selection",
	"seven_hop_choice",
	"cancel_move_selection",
})

app.mount(
	"/toc/play",
	StaticFiles(directory=BASE_DIR / "web", html=True),
	name="toc-frontend",
)

class DuplicateNameError(Exception):
	pass

class PlayerInputRouter:
	def __init__(self):
		self.input_queues = {}
		self.output_queues = {}
		self.recycleBin = {}
		self.pendingPrompts = {}
		self.interactiveMessageTypes = {"query-card", "query-card-exchange", "query-origin", "query-target", "query-seven-hop"}

	def register(self, player_name: str):
		if player_name in self.input_queues:
			logger.info("Attempted to re-registered a user with same name", extra={"routerId": player_name})
			raise DuplicateNameError
		else:
			logger.info("Player registered with router", extra={"routerId": player_name})
			self.input_queues[player_name] = asyncio.Queue()
			self.output_queues[player_name] = asyncio.Queue()

	def registerAgain(self, player_name: str):
		logger.info("Player re-registered with router", extra={"routerId": player_name})
		queues = self.recycleBin.pop(player_name)
		self.input_queues[player_name] = queues["in"]
		self.output_queues[player_name] = queues["out"]

	def unregister(self, player_name: str):
		if player_name not in self.input_queues:
			return

		logger.info("Player unregistered from router", extra={"routerId": player_name})
		self.recycleBin[player_name] = {
			"in": self.input_queues.pop(player_name),
			"out": self.output_queues.pop(player_name),
		}

	async def add_input(self, player_name: str, message: str):
		messageType = message.get("type") if isinstance(message, dict) else type(message).__name__
		logger.debug("Player input queued", extra={"routerId": player_name, "messageType": messageType})
		queue = self.input_queues.get(player_name)
		if queue:
			await queue.put(message)
		else:
			logger.warning("No input queue found", extra={"routerId": player_name})

	async def wait_for_input(self, player_name: str):
		while True:
			msg = await self.input_queues[player_name].get()
			pendingPrompt = self.pendingPrompts.get(player_name)

			if pendingPrompt is None:
				return msg

			requestId = msg.get("requestId") if isinstance(msg, dict) else None

			if requestId is None or requestId == pendingPrompt.get("requestId"):
				return msg

			logger.info("Ignored stale player input", extra={"routerId": player_name, "messageType": msg.get("type")})

	async def send_output(self, player_name: str, message: dict):
		if isinstance(message, dict) and message.get("type") in self.interactiveMessageTypes:
			message = message.copy()

			if "requestId" not in message:
				message["requestId"] = uuid.uuid4().hex

			self.pendingPrompts[player_name] = message.copy()

		messageType = message.get("type") if isinstance(message, dict) else type(message).__name__
		logger.debug("Player output queued", extra={"routerId": player_name, "messageType": messageType})

		queue = self.output_queues.get(player_name)
		if queue:
			await queue.put(message)
		else:
			logger.warning("No output queue found", extra={"routerId": player_name})

	async def get_output(self, player_name: str):
		return await self.output_queues[player_name].get()

	def clear_pending_prompt(self, player_name: str) -> None:
		self.pendingPrompts.pop(player_name, None)

	async def resend_pending_prompt(self, player_name: str) -> None:
		prompt = self.pendingPrompts.get(player_name)
		if prompt is not None:
			await self.send_output(player_name, prompt.copy())


class ConnectionManager:
	def __init__(self, clock: Clock = SYSTEM_CLOCK):
		self.games: Dict[str, GameSession] = {}
		self._clock = clock

	def _generate_game_id(self) -> str:
		while True:
			gameId = createJoinCode()

			if gameId not in self.games:
				return gameId

	def create_game(self, msg_router, rules: GameRules = MONTSURVENT_RULES, rulesetName: str = None) -> str:
		game_id = self._generate_game_id()
		self.games[game_id] = GameSession(game_id, msg_router, rules, rulesetName, self._clock)
		return game_id

	def get_game(self, game_id: str):
		return self.games.get(game_id)

class GameSession:
	def __init__(self, game_id: str, msg_router, rules: GameRules = MONTSURVENT_RULES, rulesetName: str = None, clock: Clock = SYSTEM_CLOCK):
		self.id = game_id
		self._sessionId = createSessionId()
		self._rules = rules
		self._rulesetName = rulesetName if rulesetName is not None else get_matching_preset_name(rules)
		self.players: Dict = {}
		self.started = False
		self.lock = asyncio.Lock()
		self.setupLock = asyncio.Lock()
		self.router = msg_router
		self.order: List = []
		self.game = None
		self._clock = clock
		self._createdAt = clock.utcNow()
		self._createdMonotonic = clock.monotonic()
		self._startedAt = None
		self._endedAt = None
		self._lastActivityAt = self._createdAt
		self._lastActivityMonotonic = self._createdMonotonic

	@property
	def sessionId(self) -> str:
		return self._sessionId

	@property
	def joinCode(self) -> str:
		return self.id
		
	@property
	def rules(self) -> GameRules:
		return self._rules

	@property
	def rulesetName(self) -> str:
		return self._rulesetName

	@property
	def createdAt(self):
		return self._createdAt

	@property
	def startedAt(self):
		return self._startedAt

	@property
	def endedAt(self):
		return self._endedAt

	@property
	def lastActivityAt(self):
		return self._lastActivityAt

	def lobbyAgeSeconds(self) -> float:
		return self._clock.monotonic() - self._createdMonotonic

	def inactivitySeconds(self) -> float:
		return self._clock.monotonic() - self._lastActivityMonotonic

	def recordActivity(self) -> None:
		self._lastActivityAt = self._clock.utcNow()
		self._lastActivityMonotonic = self._clock.monotonic()

	def markStarted(self) -> None:
		if self._startedAt is not None:
			return

		self._startedAt = self._clock.utcNow()
		self._lastActivityAt = self._startedAt
		self._lastActivityMonotonic = self._clock.monotonic()
		self.started = True

	def markEnded(self) -> None:
		if self._endedAt is not None:
			return

		self._endedAt = self._clock.utcNow()
		self._lastActivityAt = self._endedAt
		self._lastActivityMonotonic = self._clock.monotonic()

	def ruleset_state(self) -> dict:
		return {"preset": self._rulesetName, "values": self._rules.to_dict()}

	def metadataState(self) -> SessionMetadataState:
		return SessionMetadataState.fromGameSession(self)

	def fullUI(self) -> dict:
		if self.game:
			if self.game.activePlayer:
				active_player_name = self.game.activePlayer.name
			else:
				active_player_name = ""

			return {
				"type": "full-ui-state", 
				"players": [
						{
						"name": self.players[p]["name"], 
						"team": self.players[p]["team"], 
						"color": self.players[p]["color"], 
						"number_of_cards": self.players[p]["object"].hand.size
						}
					for p in self.players
					], 
				"pieces": self.game.board.getAllPiecesOnTheBoard(), 
				"active_player": active_player_name,
				"trackRegionLength": self._rules.track_region_length,
				"enterHouseAtSpot": self._rules.enter_house_at_spot,
				"ruleset": self.ruleset_state()
				}
		else:
			return {
				"type": "full-ui-state", 
				"players": [
						{
						"name": self.players[p]["name"], 
						"team": self.players[p]["team"], 
						"color": self.players[p]["color"], 
						"number_of_cards": self.players[p]["object"].hand.size
						}
					for p in self.players
					], 
				"pieces": [], 
				"active_player": "",
				"trackRegionLength": self._rules.track_region_length,
				"enterHouseAtSpot": self._rules.enter_house_at_spot,
				"ruleset": self.ruleset_state()
				}


	def team_is_full(self, team: str) -> bool:
		return sum([self.players[p]["team"] == team for p in self.players]) >= NUMBER_OF_PLAYERS // NUMBER_OF_TEAMS

	def is_full(self) -> bool:
		return len(self.players) >= NUMBER_OF_PLAYERS

	def available_colors(self) -> list[str]:
		usedColors = {playerData["color"] for playerData in self.players.values() if playerData.get("color")}
		return [color for color in COLORS if color not in usedColors]

	def lobby_state(self) -> dict:
		players = [
				{
				"name": playerData["name"], 
				"team": playerData.get("team", ""), 
				"color": playerData.get("color", ""), 
				"connected": playerData.get("active", False), 
				"configured": playerData.get("configured", False)
				} 
			for playerData in self.players.values()
			]

		teamCounts = {
			team: sum(playerData.get("team") == team for playerData in self.players.values()) for team in ["0", "1"]
			}
		
		return {
			"type": "lobby-state", 
			"gameId": self.id, 
			"started": self.started, 
			"players": players, 
			"availableColors": self.available_colors(), 
			"teamCounts": teamCounts, 
			"teamCapacity": NUMBER_OF_PLAYERS // NUMBER_OF_TEAMS,
			"trackRegionLength": self._rules.track_region_length,
			"enterHouseAtSpot": self._rules.enter_house_at_spot,
			"ruleset": self.ruleset_state()
			}

	async def broadcast_lobby_state(self) -> None:
		await self.broadcast(self.lobby_state())

	def getFullPlayerId(self, game_id : str, player_name : str) -> str:
		return f'{game_id}-{player_name}'

	def set_player_order(self) -> bool:
		if len(self.players) != NUMBER_OF_PLAYERS:
			return False

		playerIds = list(self.players.keys())
		firstPlayerId = playerIds[0]
		firstTeam = self.players[firstPlayerId]["team"]

		teammateIds = [playerId for playerId in playerIds if playerId != firstPlayerId and self.players[playerId]["team"] == firstTeam]
		opponentIds = [playerId for playerId in playerIds if self.players[playerId]["team"] != firstTeam]

		if len(teammateIds) != 1 or len(opponentIds) != 2:
			return False

		self.order = [firstPlayerId, opponentIds[0], teammateIds[0], opponentIds[1]]
		return True

	async def broadcast(self, message: Dict, excluded_player : str = None):
		for player_id in self.players.keys():
			if player_id != excluded_player:
				player = self.players[player_id]['object']
				await player.send_message_to_user(message)

	async def game_loop(self):
		try:
			await self.broadcast(build_message("log", "gameplay.game_starting", "Four players have joined: the game is starting!"))
			self.game = Game(self, [self.players[player_id]["color"] for player_id in self.order], self._rules)
			self.game.setPlayers([self.players[player_id]["object"] for player_id in self.order])
			await self.game.start()
		except Exception:
			logging.exception("Game loop failed for game %s", self.id)
			await self.broadcast(build_message("error", "errors.internal_game_error", "The game stopped because of an internal server error."))

	async def start_game_if_ready(self) -> bool:
		async with self.lock:
			if self.started or len(self.players) != NUMBER_OF_PLAYERS or len(self.order) != NUMBER_OF_PLAYERS:
				return False

			if not all(player.get("configured", False) for player in self.players.values()):
				return False

			self.markStarted()

		await self.broadcast_lobby_state()
		self.gameTask = asyncio.create_task(self.game_loop())
		return True

	async def configure_player(self, player_id: str, team: str, color: str) -> bool:
		async with self.setupLock:
			playerData = self.players.get(player_id)

			if playerData is None or self.started:
				return False

			if playerData.get("configured", False):
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.already_confirmed",
					"Your lobby choices have already been confirmed.",
				))
				return False

			if team not in ["0", "1"]:
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.invalid_team",
					"Please choose a valid team.",
				))
				return False

			if color not in COLORS:
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.invalid_color",
					"Please choose a valid colour.",
				))
				return False

			if self.team_is_full(team):
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.team_full",
					f"Team {team} is already full.",
					{"team": team},
				))
				return False

			if color not in self.available_colors():
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.color_taken",
					f"The colour {color} has already been selected.",
					{"color": color},
				))
				return False

			player = playerData["object"]
			player.setTeam(team)
			player.setColor(color)
			playerData["team"] = team
			playerData["color"] = color
			playerData["configured"] = True

			if len(self.players) == NUMBER_OF_PLAYERS and all(data.get("configured", False) for data in self.players.values()):
				if not self.set_player_order():
					raise RuntimeError("Could not determine a valid player order")

		await self.broadcast_lobby_state()
		await self.start_game_if_ready()
		return True

	async def handle_player_message(self, player_id: str, message: dict) -> None:
		messageType = message.get("type")

		if messageType == "configure-player":
			await self.configure_player(player_id, message.get("team", ""), message.get("color", ""))
			return

		if messageType == "debug":
			if message.get("msg") == "simulate_card_exchange_players3and4":
				playerIds = list(self.players.keys())
				player3 = self.players[playerIds[2]]["object"]
				player4 = self.players[playerIds[3]]["object"]

				await self.router.add_input(playerIds[2], {"type": "card_selection", "name": playerIds[2], "value": player3.hand.cards[0].value, "suit": player3.hand.cards[0].suit})
				await self.router.add_input(playerIds[3], {"type": "card_selection", "name": playerIds[3], "value": player4.hand.cards[0].value, "suit": player4.hand.cards[0].suit})

			elif message.get("msg") == "force-play" and self.game is not None and self.game.activePlayer is not None:
				await self.game.activePlayer.forceRandomMove()

			return

		await self.router.add_input(player_id, message)

@app.websocket("/toc/ws/{game_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_name: str):
	await websocket.accept()
	gameSession = manager.games.get(game_id)

	if gameSession is None:
		await websocket.close(code=4001)
		return

	player_id = gameSession.getFullPlayerId(game_id, player_name)
	existingPlayer = gameSession.players.get(player_id)

	if existingPlayer is not None and existingPlayer["active"]:
		await websocket.close(code=4002)
		return

	if existingPlayer is None and gameSession.is_full():
		await websocket.close(code=4004)
		return

	try:
		identityData = await asyncio.wait_for(websocket.receive_text(), timeout=IDENTIFY_TIMEOUT_SECONDS)
	except TimeoutError:
		await websocket.close(code=4005, reason="Connection identification timed out")
		return
	except WebSocketDisconnect:
		return

	try:
		identityMessage = json.loads(identityData)
	except json.JSONDecodeError:
		await websocket.close(code=4005, reason="Invalid connection identity")
		return

	if not isinstance(identityMessage, dict) or identityMessage.get("type") != "identify":
		await websocket.close(code=4005, reason="Invalid connection identity")
		return

	resumeToken = identityMessage.get("resumeToken")

	if resumeToken is not None and not isinstance(resumeToken, str):
		await websocket.close(code=4005, reason="Invalid connection identity")
		return

	if existingPlayer is not None and not resumeTokenMatches(resumeToken, existingPlayer["resumeTokenHash"]):
		await websocket.close(code=4005, reason="Invalid resume token")
		return

	try:
		if existingPlayer is None:
			persistentPlayerId = createPlayerId()
			resumeToken = createResumeToken()

			router.register(player_id)

			newPlayer = Player(player_id, player_name, "", "", "", gameSession, router)

			gameSession.players[player_id] = {
				"name": player_name,
				"id": player_id,
				"playerId": persistentPlayerId,
				"resumeTokenHash": hashResumeToken(resumeToken),
				"websocket": websocket,
				"team": "",
				"color": "",
				"object": newPlayer,
				"active": True,
				"configured": False,
			}
		else:
			persistentPlayerId = existingPlayer["playerId"]

			router.registerAgain(player_id)
			existingPlayer["websocket"] = websocket
			existingPlayer["active"] = True

	except (DuplicateNameError, KeyError):
		await websocket.close(code=4003)
		return

	async def input_loop() -> None:
		while True:
			data = await websocket.receive_text()

			try:
				message = json.loads(data)
			except json.JSONDecodeError:
				await router.send_output(player_id, build_message("error", "errors.invalid_json_message", "The server received an invalid JSON message."))
				continue

			if not isinstance(message, dict):
				await router.send_output(player_id, build_message("error", "errors.invalid_message_format", "The server received an invalid message format."))
				continue

			messageType = message.get("type")

			if not isinstance(messageType, str):
				await router.send_output(player_id, build_message("error", "errors.invalid_message_format", "Invalid message format."))
				continue

			if messageType not in CLIENT_MESSAGE_TYPES:
				await router.send_output(player_id, build_message(
					"error",
					"errors.unknown_message_type",
					f"Unknown message type: {messageType}.",
					{"messageType": messageType},
				))
				continue

			await gameSession.handle_player_message(player_id, message)

	async def output_loop() -> None:
		while True:
			message = await router.get_output(player_id)
			await websocket.send_json(message)

	async def setup_connection() -> None:
		if existingPlayer is None:
			await gameSession.broadcast_lobby_state()

		else:
			if gameSession.started:
				await existingPlayer["object"].send_message_to_user(gameSession.lobby_state())
				await existingPlayer["object"].send_message_to_user(gameSession.fullUI())
				await existingPlayer["object"].send_message_to_user(build_message(
					"log",
					"connection.rejoined_self",
					f"You successfully rejoined the game in team {existingPlayer['team']} with colour {existingPlayer['color']}!",
					{"team": existingPlayer["team"], "color": existingPlayer["color"]},
				))
				await existingPlayer["object"].sendHandAgain()
				await router.resend_pending_prompt(player_id)
				await gameSession.broadcast(build_message("log", "connection.player_rejoined", f"{player_name} rejoined the game.", {"player": player_name}), excluded_player=player_id)
			else:
				await gameSession.broadcast_lobby_state()

		await gameSession.start_game_if_ready()

	try:
		await websocket.send_json({
			"type": "ready",
			"protocolVersion": WEBSOCKET_PROTOCOL_VERSION,
			"sessionId": gameSession.sessionId,
			"playerId": persistentPlayerId,
			"resumeToken": resumeToken,
		})

		async with asyncio.TaskGroup() as taskGroup:
			taskGroup.create_task(input_loop())
			taskGroup.create_task(output_loop())
			await setup_connection()

	except* WebSocketDisconnect:
		pass

	except* Exception as errors:
		for error in errors.exceptions:
			logger.error(
				"WebSocket connection failed",
				exc_info=(type(error), error, error.__traceback__),
				extra={
					"sessionId": gameSession.sessionId,
					"joinCode": gameSession.joinCode,
					"routerId": player_id,
					"playerName": player_name,
				},
			)

	finally:
		playerData = gameSession.players.get(player_id)

		if playerData is not None and playerData.get("websocket") is websocket:
			playerData["active"] = False
			router.unregister(player_id)

			if gameSession.started:
				await gameSession.broadcast(build_message("log", "connection.player_disconnected", f"{player_name} disconnected.", {"player": player_name}), excluded_player=player_id)
			else:
				await gameSession.broadcast_lobby_state()


router = PlayerInputRouter()
manager = ConnectionManager()

@app.get("/toc")
async def root():
	return {"message": "Game backend is running."}

@app.get("/toc/api/rule-presets")
async def get_rule_presets():
	return {
		"default": DEFAULT_RULE_PRESET,
		"presets": {name: rules.to_dict() for name, rules in RULE_PRESETS.items()},
		"schema": get_rule_schema(),
		"messageKeys": sorted(MESSAGE_KEYS),
	}

@app.post("/toc/api/create-game")
async def create_game(payload = None):
	if payload is None:
		payload = {}

	if type(payload) is not dict:
		detail = build_message("http-error", "errors.creation_data_object", "Game creation data must be an object.")
		raise HTTPException(status_code=422, detail=detail)

	unknownFields = set(payload) - {"preset", "rules"}

	if unknownFields:
		fields = ", ".join(sorted(unknownFields))
		detail = build_message("http-error", "errors.unknown_creation_fields", f"Unknown game creation fields: {fields}", {"fields": fields})
		raise HTTPException(status_code=422, detail=detail)

	presetName = payload.get("preset", DEFAULT_RULE_PRESET)

	try:
		rules = resolve_ruleset(presetName, payload.get("rules"))
	except ValueError as error:
		detail = build_message("http-error", "errors.invalid_game_configuration", str(error))
		raise HTTPException(status_code=422, detail=detail) from error

	game_id = manager.create_game(router, rules, presetName)
	return {"game_id": game_id, "preset": presetName, "rules": rules.to_dict()}