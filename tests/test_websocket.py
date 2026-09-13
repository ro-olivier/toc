from contextlib import ExitStack
from threading import Event

import pytest

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from toc.application import app
from toc.runtime import manager, router
from toc.model.audit import GameEventType
from toc.infrastructure.identity import resumeTokenMatches
from toc.model.game_mode import GameMode, getGameModeDefinition
from toc.model.game import Game
from toc.model.rules import resolveRuleset
from settings import INVALID_PLAYER_NAME_CODE, MAX_PLAYER_NAME_LENGTH


PLAYER_NAMES = ["Alice", "Bob", "Carol", "Diana"]


@pytest.fixture
def client():
	with TestClient(app) as testClient:
		yield testClient


@pytest.fixture
def gameId():
	createdGameId = manager.createGame(router)

	try:
		yield createdGameId
	finally:
		session = manager.games.pop(createdGameId, None)

		if session is not None:
			for playerId in session.participants:
				router.inputQueues.pop(playerId, None)
				router.outputQueues.pop(playerId, None)
				router.recycleBin.pop(playerId, None)
				router.pendingPrompts.pop(playerId, None)

@pytest.fixture
def duelTwoGameId():
	modeDefinition = getGameModeDefinition(GameMode.DUEL_TWO)
	createdGameId = manager.createGame(router, modeDefinition=modeDefinition)

	try:
		yield createdGameId
	finally:
		session = manager.games.pop(createdGameId, None)

		if session is not None:
			for playerId in session.participants:
				router.inputQueues.pop(playerId, None)
				router.outputQueues.pop(playerId, None)
				router.recycleBin.pop(playerId, None)
				router.pendingPrompts.pop(playerId, None)

@pytest.fixture
def teamSixGameId():
	modeDefinition = getGameModeDefinition(GameMode.TEAM_SIX)
	createdGameId = manager.createGame(router, modeDefinition=modeDefinition)

	try:
		yield createdGameId
	finally:
		session = manager.games.pop(createdGameId, None)

		if session is not None:
			for playerId in session.participants:
				router.inputQueues.pop(playerId, None)
				router.outputQueues.pop(playerId, None)
				router.recycleBin.pop(playerId, None)
				router.pendingPrompts.pop(playerId, None)

def receiveLobbyState(websocket):
	state = websocket.receive_json()
	assert state["type"] == "lobby-state"
	return state


def getLobbyPlayer(state, playerName):
	return next(player for player in state["players"] if player["name"] == playerName)

def connectPlayers(stack, client, gameId, playerNames):
	sockets = {}

	for expectedPlayerCount, playerName in enumerate(playerNames, start=1):
		websocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/{playerName}"))
		sockets[playerName] = websocket

		ready = identifyWebSocket(websocket)

		for connectedSocket in sockets.values():
			state = receiveLobbyState(connectedSocket)
			assert len(state["players"]) == expectedPlayerCount

	return sockets


def identifyWebSocket(websocket, resumeToken=None):
	websocket.send_json({
		"type": "identify",
		"resumeToken": resumeToken,
	})

	ready = websocket.receive_json()

	assert ready["type"] == "ready"
	assert ready["protocolVersion"] == 2

	return ready


def assertWebSocketClosesWith(websocket, expectedCode):
	with pytest.raises(WebSocketDisconnect) as closedConnection:
		websocket.receive_json()

	assert closedConnection.value.code == expectedCode


def test_valid_websocket_connection_receives_ready_and_lobby_state(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		ready = identifyWebSocket(websocket)
		lobbyState = receiveLobbyState(websocket)

		assert ready["sessionId"] == manager.games[gameId].sessionId
		assert lobbyState["gameId"] == gameId
		assert lobbyState["started"] is False
		assert len(lobbyState["players"]) == 1
		assert lobbyState["players"][0]["name"] == "Alice"
		assert lobbyState["players"][0]["connected"] is True

		sessionParticipant = manager.games[gameId].participants[f"{gameId}-Alice"]

		assert sessionParticipant.primaryPlayer.identifier == ready["playerId"]
		assert sessionParticipant.primaryPlayer.routerId == f"{gameId}-Alice"

		participant = manager.games[gameId].roster.getParticipantByRouterId(f"{gameId}-Alice")

		assert participant is sessionParticipant.participant
		assert participant.participantId == ready["playerId"]
		assert participant.name == "Alice"
		assert participant.active is True
		assert participant.websocket is not None


def test_unknown_game_closes_websocket_with_4001(client):
	with client.websocket_connect("/toc/ws/DOES-NOT-EXIST/Alice") as websocket:
		assertWebSocketClosesWith(websocket, 4001)


def test_duplicate_active_player_name_closes_websocket_with_4002(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as firstConnection:
		identifyWebSocket(firstConnection)
		receiveLobbyState(firstConnection)

		with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as duplicateConnection:
			assertWebSocketClosesWith(duplicateConnection, 4002)


def test_fifth_player_closes_websocket_with_4004(client, gameId):
	with ExitStack() as connections:
		for playerName in PLAYER_NAMES:
			websocket = connections.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/{playerName}"))
			identifyWebSocket(websocket)

		with client.websocket_connect(f"/toc/ws/{gameId}/Erin") as fifthConnection:
			assertWebSocketClosesWith(fifthConnection, 4004)

def test_invalid_json_returns_error_and_connection_remains_open(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		ready = identifyWebSocket(websocket)
		assert websocket.receive_json()["type"] == "lobby-state"

		websocket.send_text("{not-valid-json")

		error = websocket.receive_json()

		assert error["type"] == "error"
		assert error["messageKey"] == "errors.invalid_json_message"
		assert error["fallback"] == "The server received an invalid JSON message."
		assert "msg" not in error

		websocket.send_text("[]")

		secondError = websocket.receive_json()

		assert secondError["type"] == "error"
		assert secondError["messageKey"] == "errors.invalid_message_format"

def test_non_object_message_is_rejected(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json(["configure-player"])

		error = websocket.receive_json()

		assert error["type"] == "error"
		assert error["messageKey"] == "errors.invalid_message_format"
		assert error["fallback"] == "The server received an invalid message format."

def test_message_without_type_is_rejected(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json({"team": "0", "color": "red"})

		error = websocket.receive_json()

		assert error["type"] == "error"
		assert error["messageKey"] == "errors.invalid_message_format"

def test_unknown_message_type_is_rejected(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json({"type": "explode-server"})

		error = websocket.receive_json()

		assert error["type"] == "error"
		assert error["messageKey"] == "errors.unknown_message_type"
		assert error["parameters"] == {"messageType": "explode-server"}
		assert error["fallback"] == "Unknown message type: explode-server."
		assert "msg" not in error

def test_valid_player_configuration_is_broadcast_to_every_player(client, gameId):
	with ExitStack() as stack:
		aliceSocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/Alice"))

		identifyWebSocket(aliceSocket)
		receiveLobbyState(aliceSocket)

		bobSocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/Bob"))

		identifyWebSocket(bobSocket)

		receiveLobbyState(aliceSocket)
		receiveLobbyState(bobSocket)

		aliceSocket.send_json({"type": "configure-player", "team": "0", "color": "red"})

		aliceState = receiveLobbyState(aliceSocket)
		bobState = receiveLobbyState(bobSocket)

		assert aliceState == bobState

		alice = getLobbyPlayer(aliceState, "Alice")

		assert alice["configured"] is True
		assert alice["team"] == "0"
		assert alice["color"] == "red"
		assert "red" not in aliceState["availableColors"]
		assert aliceState["teamCounts"]["0"] == 1

def test_two_players_cannot_select_the_same_color(client, gameId):
	with ExitStack() as stack:
		aliceSocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/Alice"))

		identifyWebSocket(aliceSocket)
		receiveLobbyState(aliceSocket)

		bobSocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/Bob"))

		identifyWebSocket(bobSocket)
		receiveLobbyState(aliceSocket)
		receiveLobbyState(bobSocket)

		aliceSocket.send_json({"type": "configure-player", "team": "0", "color": "red"})

		receiveLobbyState(aliceSocket)
		receiveLobbyState(bobSocket)

		bobSocket.send_json({"type": "configure-player", "team": "1", "color": "red"})

		error = bobSocket.receive_json()

		assert error["type"] == "lobby-error"
		assert error["messageKey"] == "lobby.errors.color_taken"
		assert error["parameters"] == {"color": "red"}
		assert "fallback" in error
		assert "msg" not in error

def test_team_cannot_exceed_its_capacity(client, gameId):
	with ExitStack() as stack:
		aliceSocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/Alice"))

		identifyWebSocket(aliceSocket)
		receiveLobbyState(aliceSocket)

		bobSocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/Bob"))

		identifyWebSocket(bobSocket)
		receiveLobbyState(aliceSocket)
		receiveLobbyState(bobSocket)

		carolSocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/Carol"))

		identifyWebSocket(carolSocket)
		receiveLobbyState(aliceSocket)
		receiveLobbyState(bobSocket)
		receiveLobbyState(carolSocket)

		aliceSocket.send_json({"type": "configure-player", "team": "0", "color": "red"})

		receiveLobbyState(aliceSocket)
		receiveLobbyState(bobSocket)
		receiveLobbyState(carolSocket)

		bobSocket.send_json({"type": "configure-player", "team": "0", "color": "blue"})

		receiveLobbyState(aliceSocket)
		receiveLobbyState(bobSocket)
		receiveLobbyState(carolSocket)

		carolSocket.send_json({"type": "configure-player", "team": "0", "color": "green"})

		error = carolSocket.receive_json()

		assert error["type"] == "lobby-error"
		assert error["messageKey"] == "lobby.errors.team_full"
		assert error["parameters"] == {"team": "0"}
		assert "fallback" in error
		assert "msg" not in error

def test_invalid_team_is_rejected(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json({"type": "configure-player", "team": "invalid", "color": "red"})

		error = websocket.receive_json()

		assert error["type"] == "lobby-error"
		assert error["messageKey"] == "lobby.errors.invalid_team"
		assert "fallback" in error
		assert "msg" not in error

def test_invalid_color_is_rejected(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json({"type": "configure-player", "team": "0", "color": "ultraviolet"})

		error = websocket.receive_json()

		assert error["type"] == "lobby-error"
		assert error["messageKey"] == "lobby.errors.invalid_color"
		assert "fallback" in error
		assert "msg" not in error

def test_extended_color_is_accepted(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json({"type": "configure-player", "team": "0", "color": "purple"})

		state = websocket.receive_json()

		assert state["type"] == "lobby-state"
		alice = next(player for player in state["players"] if player["name"] == "Alice")
		assert alice["configured"] is True
		assert alice["color"] == "purple"

def test_configured_lobby_player_can_reconnect(client, gameId):
	playerId = f"{gameId}-Alice"
	session = manager.games[gameId]

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		firstReady = identifyWebSocket(websocket)
		resumeToken = firstReady["resumeToken"]
		receiveLobbyState(websocket)

		websocket.send_json({"type": "configure-player", "team": "0", "color": "red"})

		state = receiveLobbyState(websocket)
		alice = getLobbyPlayer(state, "Alice")

		assert alice["configured"] is True

		originalPlayer = session.participants[playerId].primaryPlayer

	assert session.participants[playerId].active is False

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket, resumeToken)

		state = receiveLobbyState(websocket)
		alice = getLobbyPlayer(state, "Alice")

		assert alice["connected"] is True
		assert alice["configured"] is True
		assert alice["team"] == "0"
		assert alice["color"] == "red"

		assert len(state["players"]) == 1
		assert len(session.participants) == 1
		assert session.participants[playerId].primaryPlayer is originalPlayer

def test_started_game_reconnection_restores_ui_hand_and_prompt(client, gameId):
	playerId = f"{gameId}-Alice"
	session = manager.games[gameId]

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		firstReady = identifyWebSocket(websocket)
		resumeToken = firstReady["resumeToken"]

		receiveLobbyState(websocket)

		websocket.send_json({"type": "configure-player", "team": "0", "color": "red"})
		receiveLobbyState(websocket)

	assert session.participants[playerId].active is False

	session.started = True

	pendingPrompt = {
		"type": "query-card",
		"messageKey": "prompts.choose_card",
		"parameters": {},
		"fallback": "Choose a card.",
		"requestId": "test-pending-request",
	}

	router.pendingPrompts[playerId] = pendingPrompt.copy()

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		ready = identifyWebSocket(websocket, resumeToken)

		messages = [websocket.receive_json() for _ in range(5)]

		assert [message["type"] for message in messages] == [
			"lobby-state",
			"full-ui-state",
			"log",
			"reveal",
			"query-card",
		]

		lobbyState = messages[0]
		fullUIState = messages[1]
		rejoinedMessage = messages[2]
		handMessage = messages[3]
		replayedPrompt = messages[4]

		assert lobbyState["started"] is True
		assert getLobbyPlayer(lobbyState, "Alice")["connected"] is True

		assert fullUIState["players"][0]["name"] == "Alice"
		assert fullUIState["players"][0]["team"] == "0"
		assert fullUIState["players"][0]["color"] == "red"

		assert rejoinedMessage["messageKey"] == "connection.rejoined_self"
		assert "msg" not in rejoinedMessage

		assert handMessage["playerId"] == "Alice"
		assert handMessage["seatId"] == ready["playerId"]
		assert handMessage["playerColor"] == "red"
		assert "cards" in handMessage

		assert replayedPrompt == pendingPrompt
		

def test_four_configured_players_start_game_once(client, gameId, monkeypatch):
	session = manager.games[gameId]
	gameLoopCalls = []
	gameLoopStarted = Event()

	async def fakeGameLoop():
		gameLoopCalls.append(True)
		gameLoopStarted.set()

	monkeypatch.setattr(session, "gameLoop", fakeGameLoop)

	playerConfigurations = {
		"Alice": {"team": "0", "color": "red"},
		"Bob": {"team": "1", "color": "blue"},
		"Carol": {"team": "0", "color": "green"},
		"Diana": {"team": "1", "color": "yellow"},
	}

	with ExitStack() as stack:
		sockets = {}

		for expectedPlayerCount, playerName in enumerate(playerConfigurations, start=1):
			websocket = stack.enter_context(client.websocket_connect(f"/toc/ws/{gameId}/{playerName}"))
			sockets[playerName] = websocket

			ready = identifyWebSocket(websocket)

			for connectedSocket in sockets.values():
				state = receiveLobbyState(connectedSocket)

				assert state["started"] is False
				assert len(state["players"]) == expectedPlayerCount

		for playerName in ["Alice", "Bob", "Carol"]:
			sockets[playerName].send_json({
				"type": "configure-player",
				**playerConfigurations[playerName],
			})

			for connectedSocket in sockets.values():
				state = receiveLobbyState(connectedSocket)
				assert state["started"] is False

			assert session.started is False
			assert session.order == []
			assert gameLoopCalls == []

		sockets["Diana"].send_json({
			"type": "configure-player",
			**playerConfigurations["Diana"],
		})

		for connectedSocket in sockets.values():
			configuredState = receiveLobbyState(connectedSocket)
			startedState = receiveLobbyState(connectedSocket)

			assert configuredState["started"] is False
			assert startedState["started"] is True
			assert all(player["configured"] for player in startedState["players"])

		assert gameLoopStarted.wait(timeout=1)
		assert gameLoopCalls == [True]
		assert session.started is True
		assert session.order == [
			session.participants[f"{gameId}-Alice"].primarySeat.seatId,
			session.participants[f"{gameId}-Bob"].primarySeat.seatId,
			session.participants[f"{gameId}-Carol"].primarySeat.seatId,
			session.participants[f"{gameId}-Diana"].primarySeat.seatId,
		]
		assert len(session.events) == 1
		assert session.events[0].eventType is GameEventType.GAME_STARTED
		assert session.events[0].elapsedSeconds == 0

def test_started_game_broadcasts_disconnect_and_reconnect(client, gameId):
	session = manager.games[gameId]

	with client.websocket_connect(f"/toc/ws/{gameId}/Bob") as bobSocket:
		identifyWebSocket(bobSocket)
		receiveLobbyState(bobSocket)

		with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as aliceSocket:
			firstAliceReady = identifyWebSocket(aliceSocket)
			resumeAliceToken = firstAliceReady["resumeToken"]

			receiveLobbyState(bobSocket)
			receiveLobbyState(aliceSocket)

			bobSocket.send_json({"type": "configure-player", "team": "1", "color": "blue"})

			receiveLobbyState(bobSocket)
			receiveLobbyState(aliceSocket)

			aliceSocket.send_json({"type": "configure-player", "team": "0", "color": "red"})

			receiveLobbyState(bobSocket)
			receiveLobbyState(aliceSocket)

			session.started = True

		disconnectedMessage = bobSocket.receive_json()

		assert disconnectedMessage["type"] == "log"
		assert disconnectedMessage["messageKey"] == "connection.player_disconnected"
		assert disconnectedMessage["parameters"] == {"player": "Alice"}
		assert "fallback" in disconnectedMessage
		assert "msg" not in disconnectedMessage

		with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as reconnectedAliceSocket:
			identifyWebSocket(reconnectedAliceSocket, resumeAliceToken)

			aliceMessages = [reconnectedAliceSocket.receive_json() for _ in range(4)]

			assert [message["type"] for message in aliceMessages] == [
				"lobby-state",
				"full-ui-state",
				"log",
				"reveal",
			]

			aliceLobbyState = aliceMessages[0]
			aliceReconnectionMessage = aliceMessages[2]

			assert getLobbyPlayer(aliceLobbyState, "Alice")["connected"] is True
			assert aliceReconnectionMessage["messageKey"] == "connection.rejoined_self"
			assert aliceReconnectionMessage["parameters"] == {
				"team": "0",
				"color": "red",
			}
			assert "msg" not in aliceReconnectionMessage

			rejoinedBroadcast = bobSocket.receive_json()

			assert rejoinedBroadcast["type"] == "log"
			assert rejoinedBroadcast["messageKey"] == "connection.player_rejoined"
			assert rejoinedBroadcast["parameters"] == {"player": "Alice"}
			assert "fallback" in rejoinedBroadcast
			assert "msg" not in rejoinedBroadcast

def test_player_cannot_configure_lobby_twice(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json({"type": "configure-player", "team": "0", "color": "red"})

		state = receiveLobbyState(websocket)
		alice = getLobbyPlayer(state, "Alice")

		assert alice["configured"] is True
		assert alice["team"] == "0"
		assert alice["color"] == "red"

		websocket.send_json({"type": "configure-player", "team": "1", "color": "blue"})

		error = websocket.receive_json()

		assert error["type"] == "lobby-error"
		assert error["messageKey"] == "lobby.errors.already_confirmed"
		assert "fallback" in error
		assert "msg" not in error

		sessionParticipant = manager.games[gameId].participants[f"{gameId}-Alice"]

		assert sessionParticipant.team == "0"
		assert sessionParticipant.color == "red"

def test_disconnect_moves_player_queues_to_recycle_bin(client, gameId):
	playerId = f"{gameId}-Alice"
	session = manager.games[gameId]

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		assert playerId in router.inputQueues
		assert playerId in router.outputQueues
		assert playerId not in router.recycleBin
		assert session.participants[playerId].active is True

	assert session.participants[playerId].active is False
	assert playerId not in router.inputQueues
	assert playerId not in router.outputQueues
	assert playerId in router.recycleBin
	assert "in" in router.recycleBin[playerId]
	assert "out" in router.recycleBin[playerId]

def test_disconnected_player_keeps_reserved_seat(client, gameId):
	session = manager.games[gameId]

	with ExitStack() as stack:
		sockets = connectPlayers(stack, client, gameId, ["Alice", "Bob", "Carol"])

		with client.websocket_connect(f"/toc/ws/{gameId}/Diana") as dianaSocket:
			firstDianaReady = identifyWebSocket(dianaSocket)
			resumeDianaToken = firstDianaReady["resumeToken"]

			allSockets = [*sockets.values(), dianaSocket]

			for connectedSocket in allSockets:
				state = receiveLobbyState(connectedSocket)
				assert len(state["players"]) == 4

		for connectedSocket in sockets.values():
			disconnectedState = receiveLobbyState(connectedSocket)
			diana = getLobbyPlayer(disconnectedState, "Diana")

			assert diana["connected"] is False
			assert len(disconnectedState["players"]) == 4

		with client.websocket_connect(f"/toc/ws/{gameId}/Eve") as eveSocket:
			assertWebSocketClosesWith(eveSocket, 4004)

		assert len(session.participants) == 4
		assert f"{gameId}-Eve" not in session.participants

		with client.websocket_connect(f"/toc/ws/{gameId}/Diana") as reconnectedDianaSocket:
			identifyWebSocket(reconnectedDianaSocket, resumeDianaToken)

			allSockets = [*sockets.values(), reconnectedDianaSocket]

			for connectedSocket in allSockets:
				reconnectedState = receiveLobbyState(connectedSocket)
				diana = getLobbyPlayer(reconnectedState, "Diana")

				assert diana["connected"] is True
				assert len(reconnectedState["players"]) == 4

def test_game_loop_failure_is_broadcast_to_every_player(client, gameId, monkeypatch):
	class FailingGame:
		def __init__(self, *args, **kwargs):
			pass

		def setPlayers(self, players):
			pass

		async def start(self):
			raise RuntimeError("Deliberate test failure")

	monkeypatch.setattr("toc.session.game_session.Game", FailingGame)

	playerConfigurations = {
		"Alice": {"team": "0", "color": "red"},
		"Bob": {"team": "1", "color": "blue"},
		"Carol": {"team": "0", "color": "green"},
		"Diana": {"team": "1", "color": "yellow"},
	}

	with ExitStack() as stack:
		sockets = connectPlayers(stack, client, gameId, playerConfigurations.keys())

		for playerName in ["Alice", "Bob", "Carol"]:
			sockets[playerName].send_json({
				"type": "configure-player",
				**playerConfigurations[playerName],
			})

			for connectedSocket in sockets.values():
				state = receiveLobbyState(connectedSocket)
				assert state["started"] is False

		sockets["Diana"].send_json({
			"type": "configure-player",
			**playerConfigurations["Diana"],
		})

		for connectedSocket in sockets.values():
			assert receiveLobbyState(connectedSocket)["started"] is False
			assert receiveLobbyState(connectedSocket)["started"] is True

		for connectedSocket in sockets.values():
			startingMessage = connectedSocket.receive_json()
			error = connectedSocket.receive_json()

			assert startingMessage["type"] == "log"
			assert startingMessage["messageKey"] == "gameplay.game_starting"
			assert "msg" not in startingMessage

			assert error["type"] == "error"
			assert error["messageKey"] == "errors.internal_game_error"
			assert "fallback" in error
			assert "msg" not in error

def test_new_websocket_identity_is_stored_as_hash(client, gameId):

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		ready = identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		sessionParticipant = manager.games[gameId].participants[f"{gameId}-Alice"]

		assert ready["sessionId"] == manager.games[gameId].sessionId
		assert ready["playerId"] == sessionParticipant.participantId
		assert ready["resumeToken"] != sessionParticipant.resumeTokenHash
		assert resumeTokenMatches(ready["resumeToken"], sessionParticipant.resumeTokenHash)

def test_reconnection_requires_valid_resume_token(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		ready = identifyWebSocket(websocket)
		receiveLobbyState(websocket)

	resumeToken = ready["resumeToken"]

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		websocket.send_json({"type": "identify", "resumeToken": None})
		assertWebSocketClosesWith(websocket, 4005)

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		websocket.send_json({"type": "identify", "resumeToken": "incorrect-token"})
		assertWebSocketClosesWith(websocket, 4005)

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		reconnectedReady = identifyWebSocket(websocket, resumeToken)
		state = receiveLobbyState(websocket)

		assert reconnectedReady["playerId"] == ready["playerId"]
		assert reconnectedReady["resumeToken"] == resumeToken
		assert len(state["players"]) == 1

def test_resume_token_is_not_broadcast_to_other_players(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as aliceSocket:
		aliceReady = identifyWebSocket(aliceSocket)
		receiveLobbyState(aliceSocket)

		with client.websocket_connect(f"/toc/ws/{gameId}/Bob") as bobSocket:
			bobReady = identifyWebSocket(bobSocket)
			bobState = receiveLobbyState(bobSocket)
			aliceState = receiveLobbyState(aliceSocket)

			assert aliceReady["resumeToken"] != bobReady["resumeToken"]
			assert "resumeToken" not in aliceState
			assert "resumeToken" not in bobState

def test_player_cannot_reconnect_with_another_players_token(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as aliceSocket:
		aliceReady = identifyWebSocket(aliceSocket)
		receiveLobbyState(aliceSocket)

	with client.websocket_connect(f"/toc/ws/{gameId}/Bob") as bobSocket:
		bobReady = identifyWebSocket(bobSocket)
		receiveLobbyState(bobSocket)

	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as aliceSocket:
		aliceSocket.send_json({"type": "identify", "resumeToken": bobReady["resumeToken"]})

		with pytest.raises(WebSocketDisconnect) as error:
			aliceSocket.receive_json()

		assert error.value.code == 4005

def test_disconnection_updates_participant_state(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		session = manager.games[gameId]
		participant = session.roster.getParticipantByRouterId(f"{gameId}-Alice")

		assert participant.active is True
		assert participant.websocket is not None

	session = manager.games[gameId]
	sessionParticipant = session.participants[f"{gameId}-Alice"]
	participant = session.roster.getParticipantByRouterId(f"{gameId}-Alice")

	assert sessionParticipant.active is False
	assert sessionParticipant.websocket is None
	assert participant.active is False
	assert participant.websocket is None

def test_player_configuration_creates_logical_seat(client, gameId):
	with client.websocket_connect(f"/toc/ws/{gameId}/Alice") as websocket:
		ready = identifyWebSocket(websocket)
		receiveLobbyState(websocket)

		websocket.send_json({"type": "configure-player", "team": "0", "color": "red"})
		state = receiveLobbyState(websocket)

		assert getLobbyPlayer(state, "Alice")["configured"] is True

		session = manager.games[gameId]
		sessionParticipant = session.participants[f"{gameId}-Alice"]
		participant = session.roster.getParticipantByRouterId(f"{gameId}-Alice")
		seat = session.roster.getSeatById(ready["playerId"])

		assert session.roster.participantCount == 1
		assert session.roster.seatCount == 1
		assert seat is sessionParticipant.primarySeat
		assert seat.player is sessionParticipant.primaryPlayer
		assert seat.participantId == participant.participantId
		assert seat.team == "0"
		assert seat.color == "red"
		assert participant.seatIds == [seat.seatId]
		assert participant.configured is True

def test_create_game_uses_requested_game_mode(client):
	response = client.post("/toc/api/create-game", json={
		"preset": "montsurvent",
		"mode": "duel_four",
		"layout": "adjacent",
	})

	assert response.status_code == 200
	assert response.json()["gameMode"] == {
		"name": "duel_four",
		"layout": "adjacent",
	}

	gameId = response.json()["gameId"]
	session = manager.games[gameId]

	assert session.modeDefinition == getGameModeDefinition("duel_four", "adjacent")

def test_two_configured_players_start_duel_two_game(client, duelTwoGameId, monkeypatch):
	session = manager.games[duelTwoGameId]
	gameStartCalls = []
	gameStarted = Event()

	async def fakeGameStart(game):
		gameStartCalls.append(game)
		gameStarted.set()

	async def fakeFinalizeFinishedGame():
		return None

	monkeypatch.setattr(Game, "start", fakeGameStart)
	monkeypatch.setattr(session, "finalizeFinishedGame", fakeFinalizeFinishedGame)

	with ExitStack() as stack:
		sockets = connectPlayers(stack, client, duelTwoGameId, ["Alice", "Bob"])

		initialState = session.lobbyState()

		assert initialState["participantCapacity"] == 2
		assert initialState["seatCapacity"] == 2
		assert initialState["trackRegionCount"] == 2
		assert initialState["gameMode"] == {"name": "duel_two", "layout": None}
		assert initialState["ruleset"]["values"]["card_exchange"] is False
		assert initialState["ruleset"]["values"]["deal_card_counts"] == [10, 8, 8]

		sockets["Alice"].send_json({"type": "configure-player", "team": "0", "color": "red"})

		for websocket in sockets.values():
			state = receiveLobbyState(websocket)
			assert state["started"] is False

		assert session.started is False
		assert gameStartCalls == []

		sockets["Bob"].send_json({"type": "configure-player", "team": "1", "color": "blue"})

		for websocket in sockets.values():
			configuredState = receiveLobbyState(websocket)
			startedState = receiveLobbyState(websocket)

			assert configuredState["started"] is False
			assert startedState["started"] is True
			assert startedState["participantCapacity"] == 2
			assert startedState["seatCapacity"] == 2
			assert startedState["trackRegionCount"] == 2
			assert all(player["configured"] for player in startedState["players"])

		assert gameStarted.wait(timeout=1)
		assert gameStartCalls == [session.game]
		assert session.started is True
		assert len(session.order) == 2
		assert len(session.game.players) == 2
		assert session.game.board.boardSize == 36
		assert session.game.dealCardCounts == (10, 8, 8)
		assert [player.name for player in session.game.players] == ["Alice", "Bob"]

def test_six_configured_players_start_team_six_game(client, teamSixGameId, monkeypatch):
	session = manager.games[teamSixGameId]
	gameStartCalls = []
	gameStarted = Event()

	async def fakeGameStart(game):
		gameStartCalls.append(game)
		gameStarted.set()

	async def fakeFinalizeFinishedGame():
		return None

	monkeypatch.setattr(Game, "start", fakeGameStart)
	monkeypatch.setattr(session, "finalizeFinishedGame", fakeFinalizeFinishedGame)

	playerConfigurations = {
		"Alice": {"team": "0", "colors": ["red"]},
		"Bob": {"team": "1", "colors": ["blue"]},
		"Carol": {"team": "2", "colors": ["green"]},
		"Diana": {"team": "0", "colors": ["yellow"]},
		"Erin": {"team": "1", "colors": ["purple"]},
		"Frank": {"team": "2", "colors": ["orange"]},
	}

	with ExitStack() as stack:
		sockets = connectPlayers(stack, client, teamSixGameId, list(playerConfigurations))

		initialState = session.lobbyState()

		assert initialState["participantCapacity"] == 6
		assert initialState["seatCapacity"] == 6
		assert initialState["trackRegionCount"] == 6
		assert initialState["teamCapacity"] == 2
		assert initialState["teamCounts"] == {"0": 0, "1": 0, "2": 0}
		assert initialState["gameMode"] == {"name": "team_six", "layout": None}
		assert initialState["ruleset"]["values"]["card_exchange"] is True
		assert initialState["ruleset"]["values"]["deal_card_counts"] == [3, 3, 3]

		for playerName in ["Alice", "Bob", "Carol", "Diana", "Erin"]:
			sockets[playerName].send_json({
				"type": "configure-player",
				**playerConfigurations[playerName],
			})

			for websocket in sockets.values():
				state = receiveLobbyState(websocket)
				assert state["started"] is False

			assert session.started is False
			assert gameStartCalls == []

		sockets["Frank"].send_json({
			"type": "configure-player",
			**playerConfigurations["Frank"],
		})

		for websocket in sockets.values():
			configuredState = receiveLobbyState(websocket)
			startedState = receiveLobbyState(websocket)

			assert configuredState["started"] is False
			assert startedState["started"] is True
			assert startedState["participantCapacity"] == 6
			assert startedState["seatCapacity"] == 6
			assert startedState["trackRegionCount"] == 6
			assert startedState["teamCounts"] == {"0": 2, "1": 2, "2": 2}
			assert all(player["configured"] for player in startedState["players"])

		assert gameStarted.wait(timeout=1)
		assert gameStartCalls == [session.game]
		assert session.started is True
		assert len(session.order) == 6
		assert len(session.game.players) == 6
		assert session.game.board.boardSize == 108
		assert session.game.deck.expectedCardCount == 54
		assert session.game.dealCardCounts == (3, 3, 3)
		assert [player.name for player in session.game.players] == [
			"Alice",
			"Bob",
			"Carol",
			"Diana",
			"Erin",
			"Frank",
		]

		teams = session.game.getPlayersInTeams()

		assert [[player.name for player in team] for team in teams] == [
			["Alice", "Diana"],
			["Bob", "Erin"],
			["Carol", "Frank"],
		]
		assert session.game.canExchangeCards

def test_created_lobby_is_listed_and_can_be_joined_case_insensitively(client):
	gameId = None

	try:
		response = client.post("/toc/api/create-game", json={
			"creatorName": "Alice",
			"mode": "duel_two",
		})

		assert response.status_code == 200

		gameId = response.json()["gameId"]
		lobbyResponse = client.get("/toc/api/open-lobbies")

		assert lobbyResponse.status_code == 200

		listedLobby = next(lobby for lobby in lobbyResponse.json()["lobbies"] if lobby["gameName"] == gameId)

		assert listedLobby["creatorName"] == "Alice"
		assert listedLobby["playerCount"] == 0
		assert listedLobby["playerCapacity"] == 2
		assert listedLobby["mode"] == {"name": "duel_two", "layout": None}

		with client.websocket_connect(f"/toc/ws/{gameId.upper()}/Alice") as websocket:
			identifyWebSocket(websocket)
			state = receiveLobbyState(websocket)

			assert state["gameId"] == gameId
			assert state["creatorName"] == "Alice"
			assert len(state["players"]) == 1
			assert state["players"][0]["name"] == "Alice"

			updatedLobbies = client.get("/toc/api/open-lobbies").json()["lobbies"]
			updatedLobby = next(lobby for lobby in updatedLobbies if lobby["gameName"] == gameId)

			assert updatedLobby["playerCount"] == 1

	finally:
		if gameId is not None:
			session = manager.games.pop(gameId, None)

			if session is not None:
				for playerId in session.participants:
					router.forget(playerId)

@pytest.mark.parametrize("playerName", ["%20%20%20", "A" * (MAX_PLAYER_NAME_LENGTH + 1)])
def test_invalid_player_name_closes_websocket_with_4008(client, gameId, playerName):
	with client.websocket_connect(f"/toc/ws/{gameId}/{playerName}") as websocket:
		assertWebSocketClosesWith(websocket, INVALID_PLAYER_NAME_CODE)