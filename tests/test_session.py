import asyncio

from main import ConnectionManager, GameSession, PlayerInputRouter, create_game as create_game_endpoint, get_rule_presets, manager
from rules import GameRules, MONTSURVENT_RULES
from player import Player
from rules import GameRules


def add_player(session, router, name, team="", color="", configured=False, active=True):
	playerId = session.getFullPlayerId(session.id, name)
	router.register(playerId)
	player = Player(playerId, name, team=team, color=color, gameSession=session, router=router)
	session.players[playerId] = {"name": name, "id": playerId, "websocket": None, "team": team, "color": color, "object": player, "active": active, "configured": configured}
	return playerId, player


def test_connection_manager_passes_rules_to_session():
	router = PlayerInputRouter()
	manager = ConnectionManager()
	rules = GameRules(card_exchange=False)

	gameId = manager.create_game(router, rules)

	assert manager.get_game(gameId).rules is rules
	assert manager.get_game(gameId).rulesetName == "custom"

def test_rule_presets_endpoint_returns_serialized_presets():
	result = asyncio.run(get_rule_presets())

	assert result["default"] == "montsurvent"
	assert result["presets"]["montsurvent"]["rotation"] == "clockwise"
	assert result["presets"]["montsurvent"]["deal_card_counts"] == [5, 4, 4]
	assert result["schema"]["seven_hopping"]["options"] == ["disabled", "optional", "forced"]


def test_create_game_endpoint_accepts_custom_rules():
	result = asyncio.run(create_game_endpoint({"preset": "custom", "rules": {"card_exchange": False}}))
	session = manager.get_game(result["game_id"])

	try:
		assert result["preset"] == "custom"
		assert result["rules"]["card_exchange"] is False
		assert session.rules.card_exchange is False
		assert session.rulesetName == "custom"
	finally:
		manager.games.pop(result["game_id"], None)

def test_create_game_endpoint_remains_backward_compatible():
	result = asyncio.run(create_game_endpoint())
	session = manager.get_game(result["game_id"])

	try:
		assert result["preset"] == "montsurvent"
		assert session.rules is MONTSURVENT_RULES
	finally:
		manager.games.pop(result["game_id"], None)


def test_player_configuration_is_validated_and_broadcast():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		aliceId, alice = add_player(session, router, "Alice")

		assert await session.configure_player(aliceId, "0", "red")
		assert alice.team == "0"
		assert alice.color == "red"
		assert session.players[aliceId]["configured"]
		assert await router.get_output(aliceId) == session.lobby_state()

	asyncio.run(scenario())


def test_player_configuration_rejects_a_color_already_in_use():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		add_player(session, router, "Alice", team="0", color="red", configured=True)
		bobId, bob = add_player(session, router, "Bob")

		assert not await session.configure_player(bobId, "1", "red")
		assert bob.team == ""
		assert bob.color == ""
		assert await router.get_output(bobId) == {"type": "lobby-error", "msg": "The color red has already been selected."}

	asyncio.run(scenario())


def test_simultaneous_configuration_cannot_claim_the_same_color():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		aliceId, alice = add_player(session, router, "Alice")
		bobId, bob = add_player(session, router, "Bob")

		results = await asyncio.gather(session.configure_player(aliceId, "0", "red"), session.configure_player(bobId, "1", "red"))

		assert results.count(True) == 1
		assert results.count(False) == 1
		assert [alice.color, bob.color].count("red") == 1

	asyncio.run(scenario())


def test_lobby_state_reports_players_choices_and_connections():
	router = PlayerInputRouter()
	session = GameSession("TEST", router)
	add_player(session, router, "Alice", team="0", color="red", configured=True)
	add_player(session, router, "Bob", active=False)

	state = session.lobby_state()

	assert state["type"] == "lobby-state"
	assert state["gameId"] == "TEST"
	assert state["availableColors"] == ["blue", "green", "yellow"]
	assert state["teamCounts"] == {"0": 1, "1": 0}
	assert state["players"][0]["connected"]
	assert not state["players"][1]["connected"]

def test_router_preserves_queues_across_reconnection():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"

		router.register(playerId)

		inputQueue = router.input_queues[playerId]
		outputQueue = router.output_queues[playerId]

		await router.add_input(playerId, {"type": "input"})
		await router.send_output(playerId, {"type": "output"})

		router.unregister(playerId)
		router.registerAgain(playerId)

		assert router.input_queues[playerId] is inputQueue
		assert router.output_queues[playerId] is outputQueue
		assert await router.wait_for_input(playerId) == {"type": "input"}
		assert await router.get_output(playerId) == {"type": "output"}
		assert playerId not in router.recycleBin

	asyncio.run(scenario())

def test_game_session_starts_game_only_once():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)
		starts = []

		async def fake_game_loop():
			starts.append("started")

		session.game_loop = fake_game_loop
		add_player(session, router, "Alice", team="0", color="red", configured=True)
		add_player(session, router, "Bob", team="1", color="blue", configured=True)
		add_player(session, router, "Carol", team="0", color="green", configured=True)
		add_player(session, router, "Diana", team="1", color="yellow", configured=True)
		session.order = list(session.players.keys())

		results = await asyncio.gather(session.start_game_if_ready(), session.start_game_if_ready())
		await session.gameTask

		assert results.count(True) == 1
		assert results.count(False) == 1
		assert starts == ["started"]

	asyncio.run(scenario())

def test_player_order_alternates_teams():
	session = GameSession("TEST", PlayerInputRouter())
	session.players = {
		"TEST-Alice": {"team": "0"},
		"TEST-Bob": {"team": "0"},
		"TEST-Carol": {"team": "1"},
		"TEST-Diana": {"team": "1"},
	}

	assert session.set_player_order()
	assert session.order == ["TEST-Alice", "TEST-Carol", "TEST-Bob", "TEST-Diana"]


def test_player_order_rejects_invalid_teams():
	session = GameSession("TEST", PlayerInputRouter())
	session.players = {
		"TEST-Alice": {"team": "0"},
		"TEST-Bob": {"team": "0"},
		"TEST-Carol": {"team": "0"},
		"TEST-Diana": {"team": "1"},
	}

	assert not session.set_player_order()
	assert session.order == []

def test_pending_prompt_is_replayed_after_reconnection():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"
		prompt = {"type": "query-origin", "originOptions": ["red-1", "red-5"]}

		router.register(playerId)
		await router.send_output(playerId, prompt)
		sentPrompt = await router.get_output(playerId)

		assert sentPrompt["type"] == "query-origin"
		assert sentPrompt["originOptions"] == ["red-1", "red-5"]
		assert sentPrompt.get("requestId")

		router.unregister(playerId)
		router.registerAgain(playerId)
		await router.resend_pending_prompt(playerId)

		replayedPrompt = await router.get_output(playerId)
		assert replayedPrompt == sentPrompt

		router.clear_pending_prompt(playerId)
		assert playerId not in router.pendingPrompts

	asyncio.run(scenario())

def test_router_ignores_input_for_an_old_prompt():
	async def scenario():
		router = PlayerInputRouter()
		playerId = "TEST-Alice"

		router.register(playerId)
		await router.send_output(playerId, {"type": "query-target", "targetOptions": ["red-5"]})
		prompt = await router.get_output(playerId)

		staleInput = {"type": "spot_selection", "result": "red-2", "requestId": "obsolete"}
		currentInput = {"type": "spot_selection", "result": "red-5", "requestId": prompt["requestId"]}

		await router.add_input(playerId, staleInput)
		await router.add_input(playerId, currentInput)

		assert await router.wait_for_input(playerId) == currentInput

	asyncio.run(scenario())


def test_session_states_report_configured_rules():
	router = PlayerInputRouter()
	session = GameSession("TEST", router, GameRules(track_region_length=16, enter_house_at_spot=16))

	assert session.lobby_state()["trackRegionLength"] == 16
	assert session.lobby_state()["enterHouseAtSpot"] == 16
	assert session.fullUI()["trackRegionLength"] == 16
	assert session.fullUI()["enterHouseAtSpot"] == 16
	assert session.lobby_state()["ruleset"] == {"preset": "custom", "values": session.rules.to_dict()}
	assert session.fullUI()["ruleset"] == {"preset": "custom", "values": session.rules.to_dict()}