from pathlib import Path
from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import string
import random
import json
import logging
import uuid

from game import Game
from player import Player
from params import *

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent

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
		self.interactiveMessageTypes = {"query-card", "query-origin", "query-target", "query-seven-hop"}

	def register(self, player_name: str):
		if player_name in self.input_queues:
			print(f'[Router] Attempted to re-registered a user with name {player_name}!')
			raise DuplicateNameError
		else:
			print(f'[Router] Registered user {player_name}')
			self.input_queues[player_name] = asyncio.Queue()
			self.output_queues[player_name] = asyncio.Queue()

	def registerAgain(self, player_name: str):
		print(f"[Router] Reregistering user {player_name}")
		queues = self.recycleBin.pop(player_name)
		self.input_queues[player_name] = queues["in"]
		self.output_queues[player_name] = queues["out"]

	def unregister(self, player_name: str):
		if player_name not in self.input_queues:
			return

		print(f"[Router] Unregistered user {player_name}")
		self.recycleBin[player_name] = {
			"in": self.input_queues.pop(player_name),
			"out": self.output_queues.pop(player_name),
		}

	async def add_input(self, player_name: str, message: str):
		print(f"[Router] add_input called for {player_name}: {message}")
		queue = self.input_queues.get(player_name)
		if queue:
			await queue.put(message)
		else:
			print(f"[Router] No input queue found for {player_name}")

	async def wait_for_input(self, player_name: str):
		while True:
			msg = await self.input_queues[player_name].get()
			pendingPrompt = self.pendingPrompts.get(player_name)

			if pendingPrompt is None:
				return msg

			requestId = msg.get("requestId") if isinstance(msg, dict) else None

			if requestId is None or requestId == pendingPrompt.get("requestId"):
				return msg

			print(f"[Router] Ignored stale input from {player_name}: {msg}")

	async def send_output(self, player_name: str, message: dict):
		if isinstance(message, dict) and message.get("type") in self.interactiveMessageTypes:
			message = message.copy()

			if "requestId" not in message:
				message["requestId"] = uuid.uuid4().hex

			self.pendingPrompts[player_name] = message.copy()

		print(f"[Router] send_output called for {player_name}: {message}")

		queue = self.output_queues.get(player_name)
		if queue:
			await queue.put(message)
		else:
			print(f"[Router] No output queue found for {player_name}")

	async def get_output(self, player_name: str):
		return await self.output_queues[player_name].get()

	def clear_pending_prompt(self, player_name: str) -> None:
		self.pendingPrompts.pop(player_name, None)

	async def resend_pending_prompt(self, player_name: str) -> None:
		prompt = self.pendingPrompts.get(player_name)
		if prompt is not None:
			await self.send_output(player_name, prompt.copy())


class ConnectionManager:
	def __init__(self):
		self.games: Dict[str, GameSession] = {}

	def _generate_game_id(self, length=4):
		charset = string.ascii_uppercase + string.digits
		while True:
			game_id = ''.join(random.choices(charset, k=length))
			if game_id not in self.games:
				return game_id

	def create_game(self, msg_router) -> str:
		game_id = self._generate_game_id()
		self.games[game_id] = GameSession(game_id, msg_router)
		return game_id

	def get_game(self, game_id: str):
		return self.games.get(game_id)

class GameSession:
	def __init__(self, game_id: str, msg_router):
		self.id = game_id
		self.players: Dict = {}
		self.started = False
		self.lock = asyncio.Lock()
		self.setupLock = asyncio.Lock()
		self.router = msg_router
		self.order: List = []
		self.game = None

	def fullUI(self) -> dict:
		if self.game:
			if self.game.activePlayer:
				active_player_name = self.game.activePlayer.name
			else:
				active_player_name = ""

			return {"type": "full-ui-state", "players": [{"name": self.players[p]["name"], "team": self.players[p]["team"], "color": self.players[p]["color"], "number_of_cards": self.players[p]["object"].hand.size} for p in self.players], "pieces": self.game.board.getAllPiecesOnTheBoard(), "active_player": active_player_name}
		else:
			return {"type": "full-ui-state", "players": [{"name": self.players[p]["name"], "team": self.players[p]["team"], "color": self.players[p]["color"], "number_of_cards": self.players[p]["object"].hand.size} for p in self.players], "pieces": [], "active_player": ""}


	def team_is_full(self, team: str) -> bool:
		return sum([self.players[p]["team"] == team for p in self.players]) >= NUMBER_OF_PLAYERS // NUMBER_OF_TEAMS

	def is_full(self) -> bool:
		return len(self.players) >= NUMBER_OF_PLAYERS

	def available_colors(self) -> list[str]:
		usedColors = {playerData["color"] for playerData in self.players.values() if playerData.get("color")}
		return [color for color in COLORS if color not in usedColors]

	def lobby_state(self) -> dict:
		players = [{"name": playerData["name"], "team": playerData.get("team", ""), "color": playerData.get("color", ""), "connected": playerData.get("active", False), "configured": playerData.get("configured", False)} for playerData in self.players.values()]
		teamCounts = {team: sum(playerData.get("team") == team for playerData in self.players.values()) for team in ["0", "1"]}
		return {"type": "lobby-state", "gameId": self.id, "started": self.started, "players": players, "availableColors": self.available_colors(), "teamCounts": teamCounts, "teamCapacity": NUMBER_OF_PLAYERS // NUMBER_OF_TEAMS}

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
			await self.broadcast({"type": "log", "msg": "Four players have joined: game is starting!\n"})
			self.game = Game(self, [self.players[player_id]["color"] for player_id in self.order])
			self.game.setPlayers([self.players[player_id]["object"] for player_id in self.order])
			await self.game.start()
		except Exception:
			logging.exception("Game loop failed for game %s", self.id)
			await self.broadcast({"type": "error", "msg": "The game stopped because of an internal server error."})

	async def start_game_if_ready(self) -> bool:
		async with self.lock:
			if self.started or len(self.players) != NUMBER_OF_PLAYERS or len(self.order) != NUMBER_OF_PLAYERS:
				return False

			if not all(player.get("configured", False) for player in self.players.values()):
				return False

			self.started = True

		await self.broadcast_lobby_state()
		self.gameTask = asyncio.create_task(self.game_loop())
		return True

	async def configure_player(self, player_id: str, team: str, color: str) -> bool:
		async with self.setupLock:
			playerData = self.players.get(player_id)

			if playerData is None or self.started:
				return False

			if playerData.get("configured", False):
				await playerData["object"].send_message_to_user({"type": "lobby-error", "msg": "Your lobby choices have already been confirmed."})
				return False

			if team not in ["0", "1"]:
				await playerData["object"].send_message_to_user({"type": "lobby-error", "msg": "Please choose a valid team."})
				return False

			if color not in COLORS:
				await playerData["object"].send_message_to_user({"type": "lobby-error", "msg": "Please choose a valid color."})
				return False

			if self.team_is_full(team):
				await playerData["object"].send_message_to_user({"type": "lobby-error", "msg": f"Team {team} is already full."})
				return False

			if color not in self.available_colors():
				await playerData["object"].send_message_to_user({"type": "lobby-error", "msg": f"The color {color} has already been selected."})
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
	newPlayer = None

	if existingPlayer is not None and existingPlayer["active"]:
		await websocket.close(code=4002)
		return

	if existingPlayer is None and gameSession.is_full():
		await websocket.close(code=4004)
		return

	try:
		if existingPlayer is None:
			router.register(player_id)
			newPlayer = Player(player_id, player_name, "", "", "", gameSession, router)
			gameSession.players[player_id] = {"name": player_name, "id": player_id, "websocket": websocket, "team": "", "color": "", "object": newPlayer, "active": True, "configured": False}
		else:
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
				await router.send_output(player_id, {"type": "error", "msg": "Invalid JSON message."})
				continue

			if not isinstance(message, dict):
				await router.send_output(player_id, {"type": "error", "msg": "Invalid message format."})
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
				await existingPlayer["object"].send_message_to_user({"type": "log", "msg": f"You successfully rejoined the game in team {existingPlayer['team']} with color {existingPlayer['color']}!\n"})
				await existingPlayer["object"].sendHandAgain()
				await router.resend_pending_prompt(player_id)
				await gameSession.broadcast({"type": "log", "msg": f"{player_name} has rejoined the game.\n"}, excluded_player=player_id)
			else:
				await gameSession.broadcast_lobby_state()

		await gameSession.start_game_if_ready()

	try:
		await websocket.send_json({"type": "ready"})

		async with asyncio.TaskGroup() as taskGroup:
			taskGroup.create_task(input_loop())
			taskGroup.create_task(output_loop())
			await setup_connection()

	except* WebSocketDisconnect:
		pass

	except* Exception as errors:
		for error in errors.exceptions:
			logging.error("WebSocket connection failed for %s", player_id, exc_info=(type(error), error, error.__traceback__))

	finally:
		playerData = gameSession.players.get(player_id)

		if playerData is not None and playerData.get("websocket") is websocket:
			playerData["active"] = False
			router.unregister(player_id)

			if gameSession.started:
				await gameSession.broadcast({"type": "log", "msg": f"{player_name} disconnected."}, excluded_player=player_id)
			else:
				await gameSession.broadcast_lobby_state()


router = PlayerInputRouter()
manager = ConnectionManager()

@app.get("/toc")
async def root():
	return {"message": "Game backend is running."}


@app.post("/toc/api/create-game")
async def create_game():
	game_id = manager.create_game(router)
	return {"game_id": game_id}
