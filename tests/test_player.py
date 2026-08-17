import asyncio

from board import Board
from params import COLORS
from player import Player


class FakeRouter:
    def __init__(self, inputs):
        self.inputs = iter(inputs)
        self.outputs = []

    async def send_output(self, player_id, message):
        self.outputs.append((player_id, message))

    async def wait_for_input(self, player_id):
        return next(self.inputs)


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
