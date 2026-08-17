import pytest

from board import Board
from cards import Card
from params import COLORS
from player import Player


def make_player(name="Alice", color="red", team="0"):
    return Player(
        identifier=f"TEST-{name}",
        name=name,
        team=team,
        color=color,
    )


def place_piece(board, player, color, number, blocking=False):
    spot = board.getSpot(color, number)
    spot.setOccupant(player, blocking)
    player.addAPieceOnTheBoard()
    return spot


def test_new_board_contains_no_pieces():
    board = Board(COLORS)

    assert board.getAllPiecesOnTheBoard() == []


@pytest.mark.parametrize("value", ["A", "K"])
def test_ace_and_king_can_take_piece_out(value):
    board = Board(COLORS)
    player = make_player()
    player.setBoard(board)

    options = board.getMoveOptions(player, Card("♥️", value))

    exit_spot = board.getFirstSpot("red")

    assert any(
        move.ID == "OUT"
        and move.originSpot == exit_spot
        and move.targetSpot == exit_spot
        for move in options
    )


def test_ordinary_card_moves_piece_forward():
    board = Board(COLORS)
    player = make_player()
    player.setBoard(board)

    origin = place_piece(board, player, "red", 5)
    target = board.getSpot("red", 7)

    options = board.getMoveOptions(player, Card("♥️", "2"))

    assert any(
        move.ID == "MOVE"
        and move.originSpot == origin
        and move.targetSpot == target
        for move in options
    )


def test_four_can_move_forward_or_backward():
    board = Board(COLORS)
    player = make_player()
    player.setBoard(board)

    origin = place_piece(board, player, "red", 8)

    options = board.getMoveOptions(player, Card("♥️", "4"))

    targets = {
        move.targetSpot
        for move in options
        if move.originSpot == origin
    }

    assert board.getSpot("red", 12) in targets
    assert board.getSpot("red", 4) in targets


def test_jack_can_switch_with_another_player():
    board = Board(COLORS)

    alice = make_player("Alice", "red", "0")
    bob = make_player("Bob", "blue", "1")

    alice.setBoard(board)
    bob.setBoard(board)

    alice_spot = place_piece(board, alice, "red", 3)
    bob_spot = place_piece(board, bob, "red", 7)

    options = board.getMoveOptions(alice, Card("♥️", "J"))

    assert any(
        move.ID == "SWITCH"
        and move.originSpot == alice_spot
        and move.targetSpot == bob_spot
        for move in options
    )


def test_piece_cannot_cross_blocking_starting_spot():
    board = Board(COLORS)

    blocker = make_player("Blocker", "red", "0")
    mover = make_player("Mover", "blue", "1")

    blocker.setBoard(board)
    mover.setBoard(board)

    place_piece(board, blocker, "red", 0, blocking=True)
    origin = place_piece(board, mover, "yellow", 15)

    options = board.getMoveOptions(mover, Card("♥️", "2"))

    blocked_target = board.getSpot("red", 0)

    assert not any(
        move.ID == "MOVE"
        and move.originSpot == origin
        and move.targetSpot == blocked_target
        for move in options
    )


@pytest.mark.xfail(
    strict=True,
    reason="House entry currently returns the wrong house",
)
def test_first_step_into_red_houses_reaches_red_house_zero():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = board.getSpot("yellow", 16)

    target = board.getHouseFromDistance(origin, 1, player)

    assert target == board.getHouse("red", 0)
