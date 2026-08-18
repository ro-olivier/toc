import asyncio

from board import Board
from cards import Card
from move import Move
from params import COLORS
from player import Player


class FakeRouter:
	def __init__(self, inputs):
		self.inputs = iter(inputs)
		self.outputs = []
		self.pendingPrompts = []

	async def send_output(self, player_id, message):
		self.outputs.append((player_id, message))

	async def wait_for_input(self, player_id):
		return next(self.inputs)

	def clear_pending_prompt(self, player_id) -> None:
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
