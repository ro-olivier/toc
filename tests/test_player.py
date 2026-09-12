import asyncio

from toc.model.board import Board
from toc.model.cards import Card
from toc.model.move import Move
from toc.model.params import COLORS
from toc.model.player import Player


class FakeRouter:
	def __init__(self, inputs):
		self.inputs = iter(inputs)
		self.outputs = []
		self.pendingPrompts = []
		self.inputRouterIds = []
		self.clearedRouterIds = []

	async def send_output(self, routerId, message):
		self.outputs.append((routerId, message))

	async def wait_for_input(self, routerId):
		self.inputRouterIds.append(routerId)
		return next(self.inputs)

	def clear_pending_prompt(self, routerId) -> None:
		self.clearedRouterIds.append(routerId)
		self.pendingPrompts = []


def make_player(router):
	return Player(identifier="TEST-Alice", name="Alice", team="0", color="red", router=router)


def test_origin_selection_accepts_house_position():
	board = Board(COLORS)
	origin = board.getHouse("red", 0)

	router = FakeRouter([
		{"type": "spot_selection", "result": str(origin)},
	])

	player = make_player(router)
	player.setBoard(board)

	result = asyncio.run(player.getOriginChoiceFromPlayer([origin]))

	assert result is origin
	assert router.outputs[0][1]["seatId"] == "TEST-Alice"
	assert router.outputs[0][1]["playerColor"] == "red"


def test_origin_selection_rejects_position_not_offered():
	board = Board(COLORS)
	origin = board.getHouse("red", 0)

	router = FakeRouter([
		{"type": "spot_selection", "result": "spot-blue-3"},
		{"type": "spot_selection", "result": str(origin)},
	])

	player = make_player(router)
	player.setBoard(board)

	result = asyncio.run(player.getOriginChoiceFromPlayer([origin]))

	assert result is origin


def test_target_selection_accepts_house_position():
	board = Board(COLORS)
	target = board.getHouse("red", 2)

	router = FakeRouter([
		{"type": "spot_selection", "result": str(target)},
	])

	player = make_player(router)
	player.setBoard(board)

	result = asyncio.run(player.getTargetChoiceFromPlayer([target]))

	assert result is target
	assert router.outputs[0][1]["seatId"] == "TEST-Alice"
	assert router.outputs[0][1]["playerColor"] == "red"


def test_origin_selection_can_cancel_when_allowed():
	board = Board(COLORS)
	origin = board.getSpot("red", 1)
	router = FakeRouter([
		{"type": "cancel_move_selection"},
	])
	player = make_player(router)
	player.setBoard(board)

	result = asyncio.run(player.getOriginChoiceFromPlayer([origin], canCancel=True))

	assert result is None
	assert router.outputs[0][1]["canCancel"] is True


def test_target_selection_can_cancel_when_allowed():
	board = Board(COLORS)
	target = board.getSpot("red", 2)
	router = FakeRouter([
		{"type": "cancel_move_selection"},
	])
	player = make_player(router)
	player.setBoard(board)

	result = asyncio.run(player.getTargetChoiceFromPlayer([target], canCancel=True))

	assert result is None
	assert router.outputs[0][1]["canCancel"] is True


def test_origin_selection_ignores_cancel_when_not_allowed():
	board = Board(COLORS)
	origin = board.getSpot("red", 1)
	router = FakeRouter([
		{"type": "cancel_move_selection"},
		{"type": "spot_selection", "result": str(origin)},
	])
	player = make_player(router)
	player.setBoard(board)

	result = asyncio.run(player.getOriginChoiceFromPlayer([origin]))

	assert result is origin
	assert router.outputs[0][1]["canCancel"] is False


def test_cancelling_origin_returns_to_card_selection():
	board = Board(COLORS)
	cardTwo = Card("♥️", "2")
	cardThree = Card("♠️", "3")
	originOne = board.getSpot("red", 1)
	originTwo = board.getSpot("red", 4)
	targetOne = board.getSpot("red", 3)
	targetTwo = board.getSpot("red", 6)
	targetThree = board.getSpot("red", 7)
	router = FakeRouter([
		{"type": "card_selection", "suit": "♥️", "value": "2"},
		{"type": "cancel_move_selection"},
		{"type": "card_selection", "suit": "♠️", "value": "3"},
	])
	player = make_player(router)
	player.setBoard(board)
	player.hand.addToHand(cardTwo)
	player.hand.addToHand(cardThree)
	options = [
		Move("MOVE", originOne, targetOne, cardTwo, player),
		Move("MOVE", originTwo, targetTwo, cardTwo, player),
		Move("MOVE", originTwo, targetThree, cardThree, player),
	]

	result = asyncio.run(player.getMoveChoiceFromPlayer(options))

	assert result is options[2]
	assert [message[1]["type"] for message in router.outputs].count("query-card") == 2


def test_card_choice_can_use_custom_prompt():
	card = Card("♥️", "2")
	router = FakeRouter([{"type": "card_selection", "suit": "♥️", "value": "2"}])
	player = make_player(router)
	player.hand.addToHand(card)

	result = asyncio.run(player.getCardChoiceFromPlayer("prompts.discard_card", "Choose one card to discard."))

	assert result == card
	assert router.outputs[0][1] == {
		"type": "query-card",
		"messageKey": "prompts.discard_card",
		"parameters": {},
		"fallback": "Choose one card to discard.",
		"playerId": "Alice",
		"seatId": "TEST-Alice",
		"playerName": "Alice",
		"playerColor": "red",
		"playerTeam": "0",
	}
	assert len(router.outputs) == 1
	assert [message[1]["type"] for message in router.outputs] == ["query-card"]

def test_card_exchange_log_uses_translation_message():
	cardGiven = Card("♥️", "2")
	cardReceived = Card("♠️", "3")
	router = FakeRouter([])
	player = make_player(router)
	player.hand.addToHand(cardGiven)

	asyncio.run(player.switchCard(cardGiven, cardReceived))

	message = router.outputs[1][1]

	assert message["type"] == "log"
	assert message["messageKey"] == "gameplay.card_exchange_complete"
	assert message["parameters"] == {"givenCard": "♥️2", "receivedCard": "♠️3"}
	assert message["fallback"]
	assert "msg" not in message
	assert message["seatId"] == "TEST-Alice"

	receivedCardMessage = router.outputs[0][1]

	assert receivedCardMessage["type"] == "receive-card-from-friend"
	assert receivedCardMessage["seatId"] == "TEST-Alice"
	assert receivedCardMessage["value"] == "3"
	assert receivedCardMessage["suit"] == "♠️"

def test_card_exchange_uses_reconnectable_prompt():
	card = Card("♥️", "2")
	router = FakeRouter([{"type": "card_selection", "suit": "♥️", "value": "2"}])
	player = make_player(router)
	player.hand.addToHand(card)

	result = asyncio.run(player.requestCardExchange())

	assert result == card

	message = router.outputs[0][1]
	assert message["type"] == "query-card-exchange"
	assert message["messageKey"] == "prompts.exchange_card"
	assert message["fallback"] == "Please choose a card to give to your teammate."
	assert "msg" not in message
	assert message["seatId"] == "TEST-Alice"
	assert message["playerColor"] == "red"

def test_player_uses_participant_router_id_for_communication():
	card = Card("♥️", "2")
	router = FakeRouter([{"type": "card_selection", "suit": "♥️", "value": "2"}])
	player = Player(identifier="seat-red", name="Alice", team="0", color="red", router=router, routerId="TEST-Alice")
	player.hand.addToHand(card)

	result = asyncio.run(player.getCardChoiceFromPlayer())

	assert result == card
	assert player.identifier == "seat-red"
	assert player.routerId == "TEST-Alice"
	assert router.outputs[0][0] == "TEST-Alice"
	assert router.inputRouterIds == ["TEST-Alice"]
	assert router.clearedRouterIds == ["TEST-Alice"]

def test_player_uses_identifier_as_router_id_by_default():
	router = FakeRouter([])
	player = Player(identifier="TEST-Alice", name="Alice", router=router)

	asyncio.run(player.send_message_to_user({"type": "test"}))

	assert player.identifier == "TEST-Alice"
	assert player.routerId == "TEST-Alice"
	assert router.outputs == [("TEST-Alice", {"type": "test"})]

def test_player_message_identity_contains_stable_seat_id():
	player = Player("seat-red", "Alice", "0", "red")

	assert player.getMessageIdentity() == {
		"playerId": "Alice",
		"seatId": "seat-red",
		"playerName": "Alice",
		"playerColor": "red",
		"playerTeam": "0",
	}


def test_prefixed_player_identity_can_describe_moved_piece_owner():
	player = Player("seat-blue", "Bob", "1", "blue")

	assert player.getMessageIdentity("moved") == {
		"movedPlayerId": "Bob",
		"movedSeatId": "seat-blue",
		"movedPlayerName": "Bob",
		"movedPlayerColor": "blue",
		"movedPlayerTeam": "1",
	}

def test_seven_hop_prompt_identifies_deciding_seat():
	board = Board(COLORS)
	router = FakeRouter([{"type": "seven_hop_choice", "result": True}])
	player = Player(identifier="seat-red", name="Alice", team="0", color="red", router=router, routerId="TEST-Alice")

	result = asyncio.run(player.getSevenHopChoiceFromPlayer(board.getSpot("red", 7), board.getSpot("blue", 7)))

	assert result is True

	message = router.outputs[0][1]

	assert message["type"] == "query-seven-hop"
	assert message["seatId"] == "seat-red"
	assert message["playerId"] == "Alice"
	assert message["playerColor"] == "red"

def test_yellow_six_prompt_offers_track_and_fourth_house_in_cross_mode():
	router = FakeRouter([
		{"type": "card_selection", "seatId": "yellow-seat", "suit": "♣️", "value": "6"},
		{"type": "spot_selection", "seatId": "yellow-seat", "result": "spot-blue-16"},
		{"type": "spot_selection", "seatId": "yellow-seat", "result": "house-yellow-3"},
	])

	board = Board(["red", "green", "blue", "yellow"])
	player = Player("yellow-seat", "Zigo", "1", "yellow", router=router, routerId="TEST-Zigo")
	player.setBoard(board)

	card = Card("♣️", "6")
	player.hand.addToHand(card)

	for position in [board.getSpot("blue", 3), board.getSpot("blue", 16)]:
		position.setOccupant(player)
		player.addAPieceOnTheBoard()

	options = board.getMoveOptions(player, card)
	result = asyncio.run(player.getMoveChoiceFromPlayer(options))

	targetPrompt = next(message for _, message in router.outputs if message["type"] == "query-target")

	assert set(targetPrompt["targetOptions"]) == {"spot-yellow-4", "house-yellow-3"}
	assert targetPrompt["seatId"] == "yellow-seat"
	assert result.ID == "ENTER"
	assert str(result.originSpot) == "spot-blue-16"
	assert str(result.targetSpot) == "house-yellow-3"