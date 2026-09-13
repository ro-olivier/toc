import asyncio
import pytest
from fastapi import HTTPException
from uuid import UUID
from fastapi.testclient import TestClient

from settings import *
from toc.application import app
from toc.runtime import manager
from toc.session.connection_manager import ConnectionManager
from toc.session.game_session import GameSession
from toc.session.input_router import PlayerInputRouter
from toc.transport.http_routes import createGame as createGameEndpoint, getRulePresets, getOpenLobbies
from toc.model.rules import GameRules, MONTSURVENT_RULES, resolveRuleset
from toc.model.player import Player
from toc.model.cards import Card
from toc.model.rules import GameRules, resolveRuleset
from toc.model.game_phase import GamePhase
from toc.model.params import AVAILABLE_COLORS
from toc.model.game import Game
from toc.model.game_mode import DuelFourLayout, GameMode, getGameModeDefinition
from toc.infrastructure.identity import createPlayerId, createResumeToken, hashResumeToken
from toc.session.roster import Participant, PlayerSeat
from toc.model.audit import GameEventType
from toc.session.session_participant import SessionParticipant


def addPlayer(session, router, name, team="", color="", configured=False, active=True):
	routerId = session.buildRouterId(session.id, name)
	participantId = createPlayerId()
	resumeTokenHash = hashResumeToken(createResumeToken())

	router.register(routerId)

	participant = Participant(
		participantId=participantId,
		routerId=routerId,
		name=name,
		resumeTokenHash=resumeTokenHash,
		active=active,
		configured=configured,
	)

	player = Player(identifier=participantId, name=name, team=team, color=color, gameSession=session, router=router, routerId=routerId)
	seat = None

	session.roster.addParticipant(participant)

	if configured:
		seat = PlayerSeat(seatId=participantId, participantId=participantId, team=team, color=color, player=player)
		session.roster.addSeat(seat)

	sessionParticipant = SessionParticipant(participant, player)

	if seat is not None:
		sessionParticipant.addSeat(seat)

	session.participants[routerId] = sessionParticipant

	return routerId, player


def test_connection_manager_passes_rules_to_session():
	router = PlayerInputRouter()
	manager = ConnectionManager()
	rules = GameRules(card_exchange=False)

	gameId = manager.createGame(router, rules)

	assert manager.getGame(gameId).rules is rules
	assert manager.getGame(gameId).rulesetName == "custom"

def test_rule_presets_endpoint_returns_serialized_presets():
	result = asyncio.run(getRulePresets())

	assert result["default"] == "montsurvent"
	assert result["presets"]["montsurvent"]["rotation"] == "clockwise"
	assert result["presets"]["montsurvent"]["deal_card_counts"] == [5, 4, 4]
	assert result["schema"]["seven_hopping"]["options"] == ["disabled", "optional", "forced"]
	assert "gameplay.piece_moved" in result["messageKeys"]
	assert "prompts.exchange_card" in result["messageKeys"]
	assert result["messageKeys"] == sorted(result["messageKeys"])


def test_create_game_endpoint_accepts_custom_rules():
	result = asyncio.run(createGameEndpoint({"preset": "custom", "rules": {"card_exchange": False}}))
	session = manager.getGame(result["gameId"])

	try:
		assert result["preset"] == "custom"
		assert result["rules"]["card_exchange"] is False
		assert session.rules.card_exchange is False
		assert session.rulesetName == "custom"
	finally:
		manager.games.pop(result["gameId"], None)

def test_create_game_endpoint_remains_backward_compatible():
	result = asyncio.run(createGameEndpoint(None))
	session = manager.getGame(result["gameId"])

	try:
		assert result["preset"] == "montsurvent"
		assert session.rules is MONTSURVENT_RULES
		assert result["gameMode"] == {"name": "team_four", "layout": None}
	finally:
		manager.games.pop(result["gameId"], None)


def test_player_configuration_is_validated_and_broadcast():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		aliceId, alice = addPlayer(session, router, "Alice")

		assert await session.configurePlayer(aliceId, "0", "red")
		assert alice.team == "0"
		assert alice.color == "red"
		assert session.participants[aliceId].configured
		assert await router.getOutput(aliceId) == session.lobbyState()

	asyncio.run(scenario())


def test_player_configuration_rejects_a_color_already_in_use():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		addPlayer(session, router, "Alice", team="0", color="red", configured=True)
		bobId, bob = addPlayer(session, router, "Bob")

		assert not await session.configurePlayer(bobId, "1", "red")
		assert bob.team == ""
		assert bob.color == ""
		message = await router.getOutput(bobId)

		assert message["type"] == "lobby-error"
		assert message["messageKey"] == "lobby.errors.color_taken"
		assert message["parameters"] == {"color": "red"}
		assert message["fallback"] == "The colour red has already been selected."
		assert "msg" not in message

	asyncio.run(scenario())


def test_simultaneous_configuration_cannot_claim_the_same_color():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		aliceId, alice = addPlayer(session, router, "Alice")
		bobId, bob = addPlayer(session, router, "Bob")

		results = await asyncio.gather(session.configurePlayer(aliceId, "0", "red"), session.configurePlayer(bobId, "1", "red"))

		assert results.count(True) == 1
		assert results.count(False) == 1
		assert [alice.color, bob.color].count("red") == 1

	asyncio.run(scenario())


def test_lobby_state_reports_players_choices_and_connections():
	router = PlayerInputRouter()
	session = GameSession("TEST", router)
	addPlayer(session, router, "Alice", team="0", color="red", configured=True)
	addPlayer(session, router, "Bob", active=False)

	state = session.lobbyState()

	assert state["type"] == "lobby-state"
	assert state["gameId"] == "TEST"
	assert state["availableColors"] == [color for color in AVAILABLE_COLORS if color != "red"]
	assert state["teamCounts"] == {"0": 1, "1": 0}
	assert state["players"][0]["connected"]
	assert not state["players"][1]["connected"]

def test_router_preserves_queues_across_reconnection():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"

		router.register(playerId)

		inputQueue = router.inputQueues[playerId]
		outputQueue = router.outputQueues[playerId]

		await router.sendOutput(playerId, {"type": "query-card"})
		prompt = await router.getOutput(playerId)

		playerInput = {
			"type": "card_selection",
			"requestId": prompt["requestId"],
		}

		assert await router.addInput(playerId, playerInput) is True

		await router.sendOutput(playerId, {"type": "output"})

		router.unregister(playerId)
		router.registerAgain(playerId)

		assert router.inputQueues[playerId] is inputQueue
		assert router.outputQueues[playerId] is outputQueue
		assert await router.waitForInput(playerId) == playerInput
		assert await router.getOutput(playerId) == {"type": "output"}
		assert playerId not in router.recycleBin

	asyncio.run(scenario())

def test_game_session_starts_game_only_once():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		starts = []

		async def fake_game_loop():
			starts.append("started")

		session.gameLoop = fake_game_loop
		addPlayer(session, router, "Alice", team="0", color="red", configured=True)
		addPlayer(session, router, "Bob", team="1", color="blue", configured=True)
		addPlayer(session, router, "Carol", team="0", color="green", configured=True)
		addPlayer(session, router, "Diana", team="1", color="yellow", configured=True)
		session.order = [sessionParticipant.primarySeat.seatId for sessionParticipant in session.participants.values()]

		results = await asyncio.gather(session.startGameIfReady(), session.startGameIfReady())
		await session.gameTask

		assert results.count(True) == 1
		assert results.count(False) == 1
		assert starts == ["started"]

	asyncio.run(scenario())

def test_player_order_alternates_teams():
	router = PlayerInputRouter()
	session = GameSession("TEST", router)

	aliceId, _ = addPlayer(session, router, "Alice", "0", "red", configured=True)
	bobId, _ = addPlayer(session, router, "Bob", "0", "blue", configured=True)
	carolId, _ = addPlayer(session, router, "Carol", "1", "green", configured=True)
	dianaId, _ = addPlayer(session, router, "Diana", "1", "yellow", configured=True)

	assert session.setPlayerOrder()
	assert session.order == [
		session.participants[aliceId].primarySeat.seatId,
		session.participants[carolId].primarySeat.seatId,
		session.participants[bobId].primarySeat.seatId,
		session.participants[dianaId].primarySeat.seatId,
	]


def test_player_order_rejects_invalid_teams():
	router = PlayerInputRouter()
	session = GameSession("TEST", router)

	addPlayer(session, router, "Alice", "0", "red", configured=True)
	addPlayer(session, router, "Bob", "0", "blue", configured=True)
	addPlayer(session, router, "Carol", "0", "green", configured=True)
	addPlayer(session, router, "Diana", "1", "yellow", configured=True)

	assert not session.setPlayerOrder()
	assert session.order == []
	
def test_pending_prompt_is_replayed_after_reconnection():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"
		prompt = {"type": "query-origin", "originOptions": ["red-1", "red-5"]}

		router.register(playerId)
		await router.sendOutput(playerId, prompt)
		sentPrompt = await router.getOutput(playerId)

		assert sentPrompt["type"] == "query-origin"
		assert sentPrompt["originOptions"] == ["red-1", "red-5"]
		assert sentPrompt.get("requestId")

		router.unregister(playerId)
		router.registerAgain(playerId)
		await router.resendPendingPrompt(playerId)

		replayedPrompt = await router.getOutput(playerId)
		assert replayedPrompt == sentPrompt

		router.clearPendingPrompt(playerId)
		assert playerId not in router.pendingPrompts

	asyncio.run(scenario())

def test_router_ignores_input_for_an_old_prompt():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"

		router.register(playerId)
		await router.sendOutput(playerId, {"type": "query-target", "targetOptions": ["red-5"]})
		prompt = await router.getOutput(playerId)

		staleInput = {"type": "spot_selection", "result": "red-2", "requestId": "obsolete"}
		currentInput = {"type": "spot_selection", "result": "red-5", "requestId": prompt["requestId"]}

		await router.addInput(playerId, staleInput)
		await router.addInput(playerId, currentInput)

		assert await router.waitForInput(playerId) == currentInput

	asyncio.run(scenario())


def test_session_states_report_configured_rules():
	router = PlayerInputRouter()
	session = GameSession("TEST", router, GameRules(track_region_length=16, enter_house_at_spot=16))

	assert session.lobbyState()["trackRegionLength"] == 16
	assert session.lobbyState()["enterHouseAtSpot"] == 16
	assert session.fullUI()["trackRegionLength"] == 16
	assert session.fullUI()["enterHouseAtSpot"] == 16
	assert session.lobbyState()["ruleset"] == {"preset": "custom", "values": session.rules.to_dict()}
	assert session.fullUI()["ruleset"] == {"preset": "custom", "values": session.rules.to_dict()}


def test_create_game_endpoint_returns_translatable_validation_error():
	with pytest.raises(HTTPException) as caughtError:
		asyncio.run(createGameEndpoint({"preset": "unknown"}))

	detail = caughtError.value.detail

	assert caughtError.value.status_code == 422
	assert detail["type"] == "http-error"
	assert detail["messageKey"] == "errors.invalid_game_configuration"
	assert detail["parameters"] == {}
	assert detail["fallback"] == "Unknown rule preset: unknown"
	assert "msg" not in detail

def test_game_session_has_separate_join_code_and_session_id():
	session = GameSession("ABCDEF", PlayerInputRouter())

	assert session.joinCode == "ABCDEF"
	assert session.id == "ABCDEF"
	assert UUID(hex=session.sessionId).hex == session.sessionId

def test_game_phase_change_preserves_current_deal_by_default():
	session = GameSession("TEST", PlayerInputRouter())

	session.setGamePhase(GamePhase.CARD_EXCHANGE, 1)
	session.setGamePhase(GamePhase.TURN_START)

	assert session.gameProgress.phase is GamePhase.TURN_START
	assert session.gameProgress.dealIndex == 1

def test_application_lifespan_runs_interrupted_game_recovery(monkeypatch):
	recoveryCalls = []

	async def fakeRecovery():
		recoveryCalls.append("recover")
		return {
			"suspended": (),
			"finished": (),
			"failed": (),
		}

	monkeypatch.setattr(manager, "recoverInterruptedGames", fakeRecovery)

	with TestClient(app):
		pass

	assert recoveryCalls == ["recover"]

def test_player_configuration_accepts_an_extended_color():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		aliceId, alice = addPlayer(session, router, "Alice")

		assert await session.configurePlayer(aliceId, "0", "purple")
		assert alice.color == "purple"
		assert session.participants[aliceId].color == "purple"

	asyncio.run(scenario())

def test_game_session_uses_team_four_mode_by_default():
	session = GameSession("TEST", PlayerInputRouter())

	assert session.modeDefinition.mode is GameMode.TEAM_FOUR
	assert session.modeDefinition.participantCount == 4
	assert session.modeDefinition.seatCount == 4
	assert session.modeDefinition.teamCount == 2


def test_connection_manager_passes_game_mode_to_session():
	router = PlayerInputRouter()
	manager = ConnectionManager()
	modeDefinition = getGameModeDefinition(GameMode.TEAM_SIX)

	gameId = manager.createGame(router, modeDefinition=modeDefinition)
	session = manager.getGame(gameId)

	assert session.modeDefinition is modeDefinition


def test_lobby_state_reports_game_mode_capacities():
	modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.CROSS)
	session = GameSession("TEST", PlayerInputRouter(), modeDefinition=modeDefinition)

	state = session.lobbyState()

	assert state["gameMode"] == {"name": "duel_four", "layout": "cross"}
	assert state["participantCapacity"] == 2
	assert state["seatCapacity"] == 4
	assert state["teamCapacity"] == 1
	assert state["teamCounts"] == {"0": 0, "1": 0}
	assert state["seatsPerParticipant"] == 2
	assert state["trackRegionCount"] == 4


def test_team_six_mode_exposes_three_teams():
	modeDefinition = getGameModeDefinition(GameMode.TEAM_SIX)
	session = GameSession("TEST", PlayerInputRouter(), modeDefinition=modeDefinition)

	state = session.lobbyState()

	assert state["gameMode"] == {"name": "team_six", "layout": None}
	assert state["participantCapacity"] == 6
	assert state["seatCapacity"] == 6
	assert state["teamCapacity"] == 2
	assert state["teamCounts"] == {"0": 0, "1": 0, "2": 0}
	assert state["seatsPerParticipant"] == 1

def test_create_game_endpoint_accepts_game_mode_and_layout():
	result = asyncio.run(createGameEndpoint({"mode": "duel_four", "layout": "cross"}))
	session = manager.getGame(result["gameId"])

	try:
		assert session.modeDefinition == getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.CROSS)
		assert result["gameMode"] == {"name": "duel_four", "layout": "cross"}
	finally:
		manager.games.pop(result["gameId"], None)


def test_create_game_endpoint_uses_team_four_by_default():
	result = asyncio.run(createGameEndpoint(None))
	session = manager.getGame(result["gameId"])

	try:
		assert session.modeDefinition == getGameModeDefinition(GameMode.TEAM_FOUR)
		assert result["gameMode"] == {"name": "team_four", "layout": None}
	finally:
		manager.games.pop(result["gameId"], None)


@pytest.mark.parametrize(
	"payload",
	[
		{"mode": "unknown"},
		{"mode": "duel_four"},
		{"mode": "team_four", "layout": "cross"},
	],
)
def test_create_game_endpoint_rejects_invalid_game_mode_configuration(payload):
	existingGameIds = set(manager.games)

	with pytest.raises(HTTPException) as caughtError:
		asyncio.run(createGameEndpoint(payload))

	assert caughtError.value.status_code == 422
	assert caughtError.value.detail["type"] == "http-error"
	assert caughtError.value.detail["messageKey"] == "errors.invalid_game_configuration"
	assert set(manager.games) == existingGameIds

@pytest.mark.parametrize(
	("mode", "layout", "expectedSchedule"),
	[
		(GameMode.DUEL_TWO, None, (10, 8, 8)),
		(GameMode.DUEL_FOUR, DuelFourLayout.CROSS, (5, 4, 4)),
		(GameMode.TEAM_FOUR, None, (5, 4, 4)),
		(GameMode.TEAM_SIX, None, (3, 3, 3)),
	],
)
def test_game_session_exposes_mode_appropriate_dealing_schedule(mode, layout, expectedSchedule):
	modeDefinition = getGameModeDefinition(mode, layout)
	session = GameSession("TEST", PlayerInputRouter(), modeDefinition=modeDefinition)

	assert session.dealCardCounts == expectedSchedule

def test_duel_four_participant_can_configure_two_seats():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		aliceId, alice = addPlayer(session, router, "Alice")

		assert await session.configurePlayer(aliceId, "0", ["red", "blue"])

		sessionParticipant = session.participants[aliceId]

		assert session.roster.seatCount == 2
		assert sessionParticipant.configured
		assert sessionParticipant.colors == ["red", "blue"]
		assert len(sessionParticipant.controlledPlayers) == 2
		assert len(sessionParticipant.controlledSeats) == 2
		assert sessionParticipant.primaryPlayer is alice
		assert sessionParticipant.primarySeat is sessionParticipant.controlledSeats[0]
		assert [seat.color for seat in sessionParticipant.controlledSeats] == ["red", "blue"]
		assert all(seat.team == "0" for seat in sessionParticipant.controlledSeats)
		assert all(player.routerId == aliceId for player in sessionParticipant.controlledPlayers)

	asyncio.run(scenario())


def test_duel_four_configuration_requires_two_colours():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.CROSS)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		aliceId, alice = addPlayer(session, router, "Alice")

		assert not await session.configurePlayer(aliceId, "0", ["red"])
		assert session.roster.seatCount == 0
		assert alice.team == ""
		assert alice.color == ""

		message = await router.getOutput(aliceId)

		assert message["type"] == "lobby-error"
		assert message["messageKey"] == "lobby.errors.invalid_color_count"
		assert message["parameters"] == {"count": 2}

	asyncio.run(scenario())


def test_multi_seat_configuration_rejects_duplicate_colours_atomically():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		aliceId, alice = addPlayer(session, router, "Alice")

		assert not await session.configurePlayer(aliceId, "0", ["red", "red"])
		assert session.roster.seatCount == 0
		assert session.participants[aliceId].controlledSeats == []
		assert alice.team == ""
		assert alice.color == ""

		message = await router.getOutput(aliceId)

		assert message["messageKey"] == "lobby.errors.invalid_color"

	asyncio.run(scenario())


def test_multi_seat_lobby_state_reports_all_selected_colours():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.CROSS)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		aliceId, _ = addPlayer(session, router, "Alice")

		assert await session.configurePlayer(aliceId, "0", ["red", "green"])

		state = await router.getOutput(aliceId)
		aliceState = state["players"][0]

		assert aliceState["color"] == "red"
		assert aliceState["colors"] == ["red", "green"]
		assert [seat["color"] for seat in aliceState["seats"]] == ["red", "green"]
		assert "red" not in state["availableColors"]
		assert "green" not in state["availableColors"]
		assert state["teamCounts"] == {"0": 1, "1": 0}

	asyncio.run(scenario())

@pytest.mark.parametrize(
	("layout", "expectedColors"),
	[
		(DuelFourLayout.ADJACENT, ["red", "blue", "green", "yellow"]),
		(DuelFourLayout.CROSS, ["red", "green", "blue", "yellow"]),
	],
)
def test_complete_duel_four_lobby_starts_with_correct_seat_order(layout, expectedColors):
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, layout)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		startCalls = []

		async def fakeGameLoop():
			startCalls.append([seat.color for seat in session.orderedSeats])

		session.gameLoop = fakeGameLoop

		aliceId, _ = addPlayer(session, router, "Alice")
		bobId, _ = addPlayer(session, router, "Bob")

		assert await session.configurePlayer(aliceId, "0", ["red", "blue"])
		assert not session.started

		assert await session.configurePlayer(bobId, "1", ["green", "yellow"])
		assert session.started
		assert session.gameTask is not None

		await session.gameTask

		assert session.roster.participantCount == 2
		assert session.roster.seatCount == 4
		assert len(session.order) == 4
		assert [seat.color for seat in session.orderedSeats] == expectedColors
		assert startCalls == [expectedColors]

	asyncio.run(scenario())

def test_duel_four_order_can_start_with_team_one():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.CROSS)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)

		async def fakeGameLoop():
			pass

		session.gameLoop = fakeGameLoop

		aliceId, _ = addPlayer(session, router, "Alice")
		bobId, _ = addPlayer(session, router, "Bob")

		assert await session.configurePlayer(aliceId, "1", ["red", "green"])
		assert await session.configurePlayer(bobId, "0", ["blue", "yellow"])

		await session.gameTask

		assert [seat.color for seat in session.orderedSeats] == ["red", "blue", "green", "yellow"]
		assert [seat.team for seat in session.orderedSeats] == ["1", "0", "1", "0"]

		assert session.lobbyState()["seatOrder"] == session.order

	asyncio.run(scenario())

def test_full_ui_state_contains_one_entry_per_logical_seat():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.CROSS)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		aliceId, _ = addPlayer(session, router, "Alice")

		assert await session.configurePlayer(aliceId, "0", ["red", "green"])

		state = session.fullUI()

		assert len(state["players"]) == 2
		assert [player["name"] for player in state["players"]] == ["Alice", "Alice"]
		assert [player["color"] for player in state["players"]] == ["red", "green"]
		assert len({player["seatId"] for player in state["players"]}) == 2
		assert all(player["participantId"] == session.participants[aliceId].participantId for player in state["players"])
		assert state["active_player"] == ""
		assert state["activeSeatId"] is None

	asyncio.run(scenario())

def test_duel_four_reconnection_replays_both_controlled_hands():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		aliceId, _ = addPlayer(session, router, "Alice")

		assert await session.configurePlayer(aliceId, "0", ["red", "blue"])

		await router.getOutput(aliceId)

		redPlayer, bluePlayer = session.participants[aliceId].controlledPlayers
		redPlayer.hand.addToHand(Card("♥️", "A"))
		bluePlayer.hand.addToHand(Card("♠️", "K"))

		await session.sendHandsAgain(session.participants[aliceId])

		redMessage = await router.getOutput(aliceId)
		blueMessage = await router.getOutput(aliceId)

		assert redMessage["type"] == "reveal"
		assert redMessage["seatId"] == redPlayer.identifier
		assert redMessage["playerColor"] == "red"
		assert redMessage["cards"] == [{"suit": "♥️", "value": "A"}]

		assert blueMessage["type"] == "reveal"
		assert blueMessage["seatId"] == bluePlayer.identifier
		assert blueMessage["playerColor"] == "blue"
		assert blueMessage["cards"] == [{"suit": "♠️", "value": "K"}]

	asyncio.run(scenario())

def test_duel_two_lobby_state_reports_two_participants_and_regions():
	modeDefinition = getGameModeDefinition(GameMode.DUEL_TWO)
	session = GameSession("TEST", PlayerInputRouter(), modeDefinition=modeDefinition)

	state = session.lobbyState()

	assert state["gameMode"] == {"name": "duel_two", "layout": None}
	assert state["participantCapacity"] == 2
	assert state["seatCapacity"] == 2
	assert state["teamCapacity"] == 1
	assert state["teamCounts"] == {"0": 0, "1": 0}
	assert state["seatsPerParticipant"] == 1
	assert state["trackRegionCount"] == 2

def test_duel_two_rejects_two_participants_on_the_same_team():
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_TWO)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		aliceId, _ = addPlayer(session, router, "Alice")

		assert await session.configurePlayer(aliceId, "0", "red")

		bobId, bob = addPlayer(session, router, "Bob")

		assert not await session.configurePlayer(bobId, "0", "blue")
		assert not session.participants[bobId].configured
		assert bob.team == ""
		assert bob.color == ""

		message = await router.getOutput(bobId)

		assert message["type"] == "lobby-error"
		assert message["messageKey"] == "lobby.errors.team_full"
		assert message["parameters"] == {"team": "0"}

	asyncio.run(scenario())

def test_complete_duel_two_lobby_builds_two_region_game(monkeypatch):
	async def scenario():
		router = PlayerInputRouter()
		modeDefinition = getGameModeDefinition(GameMode.DUEL_TWO)
		session = GameSession("TEST", router, modeDefinition=modeDefinition)
		startedGames = []

		async def fakeStart(game):
			startedGames.append({
				"colors": game.board.colors,
				"dealCardCounts": game.dealCardCounts,
				"players": tuple(player.name for player in game.players),
			})

		async def fakeFinalizeFinishedGame():
			pass

		monkeypatch.setattr(Game, "start", fakeStart)
		session.finalizeFinishedGame = fakeFinalizeFinishedGame

		aliceId, _ = addPlayer(session, router, "Alice")
		bobId, _ = addPlayer(session, router, "Bob")

		assert await session.configurePlayer(aliceId, "0", "red")
		assert not session.started

		assert await session.configurePlayer(bobId, "1", "blue")
		assert session.started
		assert session.gameTask is not None

		await session.gameTask

		assert session.roster.participantCount == 2
		assert session.roster.seatCount == 2
		assert [seat.color for seat in session.orderedSeats] == ["red", "blue"]
		assert startedGames == [{
			"colors": ("red", "blue"),
			"dealCardCounts": (10, 8, 8),
			"players": ("Alice", "Bob"),
		}]

	asyncio.run(scenario())

def test_create_game_endpoint_accepts_duel_two_mode():
	result = asyncio.run(createGameEndpoint({"mode": "duel_two"}))
	session = manager.getGame(result["gameId"])

	try:
		assert result["gameMode"] == {"name": "duel_two", "layout": None}
		assert session.modeDefinition == getGameModeDefinition(GameMode.DUEL_TWO)
		assert session.dealCardCounts == (10, 8, 8)
	finally:
		manager.games.pop(result["gameId"], None)

def test_duel_two_ruleset_state_reports_effective_mode_rules():
	modeDefinition = getGameModeDefinition(GameMode.DUEL_TWO)
	session = GameSession("TEST", PlayerInputRouter(), modeDefinition=modeDefinition)

	state = session.rulesetState()

	assert session.rules.card_exchange is True
	assert session.rules.deal_card_counts == (5, 4, 4)
	assert state["values"]["card_exchange"] is False
	assert state["values"]["deal_card_counts"] == [10, 8, 8]

def test_create_game_endpoint_accepts_team_six_mode():
	result = asyncio.run(createGameEndpoint({"mode": "team_six"}))
	session = manager.getGame(result["gameId"])

	try:
		assert session.modeDefinition == getGameModeDefinition(GameMode.TEAM_SIX)
		assert session.modeDefinition.participantCount == 6
		assert session.modeDefinition.seatCount == 6
		assert session.modeDefinition.teamCount == 3
		assert session.dealCardCounts == (3, 3, 3)
		assert result["gameMode"] == {"name": "team_six", "layout": None}
	finally:
		manager.games.pop(result["gameId"], None)

def test_team_six_ruleset_state_reports_effective_dealing_schedule():
	modeDefinition = getGameModeDefinition(GameMode.TEAM_SIX)
	session = GameSession("TEST", PlayerInputRouter(), modeDefinition=modeDefinition)

	state = session.rulesetState()

	assert state["values"]["card_exchange"] is True
	assert state["values"]["deal_card_counts"] == [3, 3, 3]

def test_connection_manager_retries_human_join_code_collision(monkeypatch):
	generatedCodes = iter(["calm-otter", "calm-otter", "brave-fox"])
	monkeypatch.setattr("toc.session.connection_manager.createJoinCode", lambda: next(generatedCodes))

	connectionManager = ConnectionManager()
	firstGameId = connectionManager.createGame(PlayerInputRouter())
	secondGameId = connectionManager.createGame(PlayerInputRouter())

	assert firstGameId == "calm-otter"
	assert secondGameId == "brave-fox"
	assert set(connectionManager.games) == {"calm-otter", "brave-fox"}

def test_connection_manager_finds_human_join_code_case_insensitively(monkeypatch):
	monkeypatch.setattr("toc.session.connection_manager.createJoinCode", lambda: "calm-otter")

	connectionManager = ConnectionManager()
	gameId = connectionManager.createGame(PlayerInputRouter())
	session = connectionManager.getGame(gameId)

	assert connectionManager.getGame("CALM-OTTER") is session
	assert connectionManager.getGame("  Calm-Otter  ") is session

def test_create_game_endpoint_stores_creator_name():
	result = asyncio.run(createGameEndpoint({
		"creatorName": "  Alice  ",
		"mode": "team_four",
	}))
	session = manager.getGame(result["gameId"])

	try:
		assert result["creatorName"] == "Alice"
		assert session.creatorName == "Alice"
		assert session.lobbyState()["creatorName"] == "Alice"
	finally:
		manager.games.pop(result["gameId"], None)

@pytest.mark.parametrize("creatorName", ["", "   ", 42, [], "A" * 41])
def test_create_game_endpoint_rejects_invalid_creator_name(creatorName):
	existingGameIds = set(manager.games)

	with pytest.raises(HTTPException) as caughtError:
		asyncio.run(createGameEndpoint({"creatorName": creatorName}))

	assert caughtError.value.status_code == 422
	assert caughtError.value.detail["type"] == "http-error"
	assert caughtError.value.detail["messageKey"] == "errors.invalid_creator_name"
	assert set(manager.games) == existingGameIds

def test_open_lobby_list_contains_only_public_information():
	router = PlayerInputRouter()
	connectionManager = ConnectionManager()
	modeDefinition = getGameModeDefinition(GameMode.DUEL_TWO)
	gameId = connectionManager.createGame(router, modeDefinition=modeDefinition, creatorName="Alice")
	session = connectionManager.getGame(gameId)

	addPlayer(session, router, "Alice")

	result = connectionManager.getOpenLobbies()

	assert result == [{
		"gameName": gameId,
		"creatorName": "Alice",
		"playerCount": 1,
		"playerCapacity": 2,
		"mode": {
			"name": "duel_two",
			"layout": None,
		},
	}]

def test_open_lobby_list_excludes_unjoinable_sessions(monkeypatch):
	router = PlayerInputRouter()
	connectionManager = ConnectionManager()
	duelMode = getGameModeDefinition(GameMode.DUEL_TWO)

	joinableId = connectionManager.createGame(router, modeDefinition=duelMode, creatorName="Joinable")
	startedId = connectionManager.createGame(router, modeDefinition=duelMode, creatorName="Started")
	fullId = connectionManager.createGame(router, modeDefinition=duelMode, creatorName="Full")
	expiredId = connectionManager.createGame(router, modeDefinition=duelMode, creatorName="Expired")

	startedSession = connectionManager.getGame(startedId)
	startedSession.markStarted()

	fullSession = connectionManager.getGame(fullId)
	addPlayer(fullSession, router, "Alice")
	addPlayer(fullSession, router, "Bob")

	expiredSession = connectionManager.getGame(expiredId)
	monkeypatch.setattr(expiredSession, "lobbyAgeSeconds", lambda: LOBBY_LIFETIME_SECONDS)

	result = connectionManager.getOpenLobbies()

	assert [lobby["gameName"] for lobby in result] == [joinableId]

def test_open_lobbies_endpoint_returns_manager_lobbies(monkeypatch):
	monkeypatch.setattr(manager, "getOpenLobbies", lambda: [{
		"gameName": "calm-otter",
		"creatorName": "Alice",
		"playerCount": 1,
		"playerCapacity": 4,
		"mode": {
			"name": "team_four",
			"layout": None,
		},
	}])

	result = asyncio.run(getOpenLobbies())

	assert result == {
		"lobbies": [{
			"gameName": "calm-otter",
			"creatorName": "Alice",
			"playerCount": 1,
			"playerCapacity": 4,
			"mode": {
				"name": "team_four",
				"layout": None,
			},
		}],
	}

def test_player_event_uses_persistent_seat_id():
	router = PlayerInputRouter()
	session = GameSession("TEST", router)
	_, player = addPlayer(session, router, "Alice", "0", "red", configured=True)

	event = session.recordPlayerEvent(GameEventType.TURN_STARTED, player, {"handSize": 5})

	assert event.playerId == session.getPersistentPlayerId(player)
	assert event.details == {"handSize": 5}

def test_router_ignores_unsolicited_and_duplicate_input():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"
		router.register(playerId)

		unsolicitedInput = {"type": "card_selection", "requestId": "unsolicited"}
		assert await router.addInput(playerId, unsolicitedInput) is False
		assert router.inputQueues[playerId].empty()

		await router.sendOutput(playerId, {"type": "query-card"})
		prompt = await router.getOutput(playerId)
		currentInput = {"type": "card_selection", "requestId": prompt["requestId"]}

		assert await router.addInput(playerId, currentInput) is True
		assert await router.addInput(playerId, currentInput) is False
		assert router.inputQueues[playerId].qsize() == 1

	asyncio.run(scenario())


def test_router_replaces_queued_input_from_an_obsolete_prompt():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"
		router.register(playerId)

		await router.sendOutput(playerId, {"type": "query-card"})
		firstPrompt = await router.getOutput(playerId)
		firstInput = {"type": "card_selection", "requestId": firstPrompt["requestId"]}
		await router.addInput(playerId, firstInput)
		assert await router.waitForInput(playerId) == firstInput

		await router.addInput(playerId, firstInput)
		router.clearPendingPrompt(playerId)
		await router.sendOutput(playerId, {"type": "query-card"})
		secondPrompt = await router.getOutput(playerId)
		secondInput = {"type": "card_selection", "requestId": secondPrompt["requestId"]}

		assert await router.addInput(playerId, secondInput) is True
		assert await router.waitForInput(playerId) == secondInput

	asyncio.run(scenario())