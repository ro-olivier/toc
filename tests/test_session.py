import asyncio

from main import GameSession, PlayerInputRouter
from player import Player


def test_team_choice_is_received_through_player_router():
	async def scenario():
		router = PlayerInputRouter()
		session = GameSession("TEST", router)

		aliceId = session.getFullPlayerId("TEST", "Alice")
		bobId = session.getFullPlayerId("TEST", "Bob")

		router.register(aliceId)
		router.register(bobId)

		alice = Player(aliceId, "Alice", team="0", color="red", router=router)
		bob = Player(bobId, "Bob", router=router)

		session.players[aliceId] = {"object": alice, "team": "0"}
		session.players[bobId] = {"object": bob, "team": ""}

		await router.add_input(bobId, {"type": "text_input", "msg": "1"})

		team = await session.make_player_choose_team(bobId)
		query = await router.get_output(bobId)
		confirmation = await router.get_output(bobId)

		assert team == "1"
		assert query["type"] == "query"
		assert confirmation["type"] == "log"

	asyncio.run(scenario())

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
		session.players = {str(index): {"configured": True} for index in range(4)}
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