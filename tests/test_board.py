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

def place_house_piece(board, player, house_number):
    house = board.getHouse(player.color, house_number)
    house.setOccupant(player)
    player.addAPieceOnTheBoard()
    return house

def test_new_board_contains_no_pieces():
    board = Board(COLORS)

    assert board.getAllPiecesOnTheBoard() == []

@pytest.mark.parametrize(
    ("distance", "house_number"),
    [
        (1, 0),
        (2, 1),
        (3, 2),
        (4, 3),
    ],
)
def test_forward_move_from_entry_reaches_expected_house(
    distance,
    house_number,
):
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    # red-0 is also the final position of yellow territory and the
    # entrance to the red house lane.
    origin = board.getFirstSpot("red")
    origin.setOccupant(player)
    player.addAPieceOnTheBoard()

    target = board.getHouseFromDistance(origin, distance, player)

    assert target == board.getHouse("red", house_number)


def test_freshly_deployed_piece_cannot_immediately_enter_house():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = board.getFirstSpot("red")
    origin.setOccupant(player, isOwnPlayerTakingAPieceOut=True)
    player.addAPieceOnTheBoard()

    target = board.getHouseFromDistance(origin, 1, player)

    assert target is None


def test_piece_cannot_overshoot_last_house_from_entry():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = board.getFirstSpot("red")
    origin.setOccupant(player)
    player.addAPieceOnTheBoard()

    target = board.getHouseFromDistance(origin, 5, player)

    assert target is None


def test_player_can_choose_between_track_and_house():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = board.getFirstSpot("red")
    origin.setOccupant(player)
    player.addAPieceOnTheBoard()

    options = board.getMoveOptions(player, Card("♥️", "2"))

    # The player may continue normally around the track.
    assert any(
        move.ID == "MOVE"
        and move.originSpot == origin
	and move.targetSpot == board.getSpotFromDistance(origin, 2)
        for move in options
    )

    # Or enter the second house position.
    assert any(
        move.ID == "ENTER"
        and move.originSpot == origin
        and move.targetSpot == board.getHouse("red", 1)
        for move in options
    )


def test_backward_four_cannot_enter_house():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = place_piece(board, player, "red", 2)

    options = board.getMoveOptions(player, Card("♥️", "4"))

    assert not any(
        move.ID == "ENTER"
        and move.originSpot == origin
        for move in options
    )


def test_piece_inside_house_can_move_forward():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = place_house_piece(board, player, 0)

    options = board.getMoveOptions(player, Card("♥️", "2"))

    assert any(
        move.ID == "ENTER"
        and move.originSpot == origin
        and move.targetSpot == board.getHouse("red", 2)
        for move in options
    )


def test_piece_inside_house_can_move_during_seven_split():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = place_house_piece(board, player, 0)

    # Value "1" is the engine's internal single-step card used while
    # constructing a seven split.
    options = board.getMoveOptions(player, Card("", "1"))

    assert any(
        move.ID == "ENTER"
        and move.originSpot == origin
        and move.targetSpot == board.getHouse("red", 1)
        for move in options
    )


def test_piece_inside_house_cannot_overshoot():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = place_house_piece(board, player, 2)

    options = board.getMoveOptions(player, Card("♥️", "2"))

    assert not any(move.originSpot == origin for move in options)


def test_piece_cannot_jump_over_occupied_house():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = place_house_piece(board, player, 0)
    place_house_piece(board, player, 1)

    options = board.getMoveOptions(player, Card("♥️", "2"))

    assert not any(
        move.ID == "ENTER"
        and move.originSpot == origin
        and move.targetSpot == board.getHouse("red", 2)
        for move in options
    )


def test_piece_cannot_land_on_occupied_house():
    board = Board(COLORS)
    player = make_player("Alice", "red")
    player.setBoard(board)

    origin = place_house_piece(board, player, 0)
    occupied_target = place_house_piece(board, player, 2)

    options = board.getMoveOptions(player, Card("♥️", "2"))

    assert not any(
        move.ID == "ENTER"
        and move.originSpot == origin
        and move.targetSpot == occupied_target
        for move in options
    )


def test_house_piece_cannot_be_used_for_jack_switch():
    board = Board(COLORS)

    alice = make_player("Alice", "red", "0")
    bob = make_player("Bob", "blue", "1")

    alice.setBoard(board)
    bob.setBoard(board)

    alice_house = place_house_piece(board, alice, 0)
    place_piece(board, bob, "blue", 5)

    options = board.getMoveOptions(alice, Card("♥️", "J"))

    assert not any(
        move.ID == "SWITCH"
        and move.originSpot == alice_house
        for move in options
    )


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


