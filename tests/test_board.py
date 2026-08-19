import pytest

from board import Board
from cards import Card
from params import COLORS
from player import Player
from move import Move
from rules import GameRules


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


def test_get_all_pieces_of_other_players_excludes_own_pieces():
	board = Board(COLORS)
	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	charlie = make_player("Charlie", "green", "0")

	aliceSpot = place_piece(board, alice, "red", 1)
	bobSpot = place_piece(board, bob, "red", 2)
	charlieSpot = place_piece(board, charlie, "red", 3)

	result = board.getAllPiecesOfOtherPlayer(alice)

	assert aliceSpot not in result
	assert result == [bobSpot, charlieSpot]

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

def test_piece_can_land_on_own_piece():
	board = Board(COLORS)
	player = make_player("Alice", "red")
	player.setBoard(board)

	origin = place_piece(board, player, "red", 5)
	occupiedTarget = place_piece(board, player, "red", 7)

	options = board.getMoveOptions(player, Card("♥️", "2"))

	assert any(
		move.ID == "MOVE"
		and move.originSpot == origin
		and move.targetSpot == occupiedTarget
		for move in options
	)

def test_seven_is_available_with_complete_open_route():
	board = Board(COLORS)
	player = make_player("Alice", "red")
	player.setBoard(board)

	place_piece(board, player, "red", 5)

	options = board.getMoveOptions(player, Card("♥️", "7"))

	assert any(move.ID == "SEVEN" for move in options)


def test_seven_is_not_available_when_only_three_house_steps_remain():
	board = Board(COLORS)
	player = make_player("Alice", "red")
	player.setBoard(board)

	place_house_piece(board, player, 0)

	options = board.getMoveOptions(player, Card("♥️", "7"))

	assert not any(move.ID == "SEVEN" for move in options)


def test_seven_is_not_available_when_only_piece_is_blocked():
	board = Board(COLORS)

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "yellow", "1")

	alice.setBoard(board)
	bob.setBoard(board)

	place_piece(board, alice, "green", 16)
	place_piece(board, bob, "yellow", 0, blocking=True)

	options = board.getMoveOptions(alice, Card("♥️", "7"))

	assert not any(move.ID == "SEVEN" for move in options)


def test_seven_search_does_not_mutate_board():
	board = Board(COLORS)
	player = make_player("Alice", "red")
	player.setBoard(board)

	origin = place_piece(board, player, "red", 5)
	stateBeforeSearch = board.getAllPiecesOnTheBoard()

	board.getSevenStepOptions(player, 7)

	assert board.getAllPiecesOnTheBoard() == stateBeforeSearch
	assert origin.occupant is player


def test_five_can_move_opponent_piece():
	board = Board(COLORS)

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")

	alice.setBoard(board)
	bob.setBoard(board)

	origin = place_piece(board, bob, "red", 5)
	target = board.getSpot("red", 10)

	options = board.getMoveOptions(alice, Card("♥️", "5"))

	assert any(
		move.ID == "FIVE"
		and move.player is alice
		and move.pieceOwner is bob
		and move.originSpot == origin
		and move.targetSpot == target
		for move in options
	)


def test_five_cannot_move_partner_piece():
	board = Board(COLORS)

	alice = make_player("Alice", "red", "0")
	partner = make_player("Partner", "green", "0")

	alice.setBoard(board)
	partner.setBoard(board)

	partnerPiece = place_piece(board, partner, "red", 5)

	options = board.getMoveOptions(alice, Card("♥️", "5"))

	assert not any(move.originSpot == partnerPiece for move in options)


def test_five_cannot_move_piece_inside_house():
	board = Board(COLORS)

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")

	alice.setBoard(board)
	bob.setBoard(board)

	housePiece = place_house_piece(board, bob, 0)

	options = board.getMoveOptions(alice, Card("♥️", "5"))

	assert not any(move.originSpot == housePiece for move in options)


def test_five_does_not_enter_opponent_house():
	board = Board(COLORS)

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")

	alice.setBoard(board)
	bob.setBoard(board)

	origin = place_piece(board, bob, "red", 16)
	expectedTarget = board.getSpotFromDistance(origin, 5)

	options = board.getMoveOptions(alice, Card("♥️", "5"))

	assert any(
		move.ID == "FIVE"
		and move.originSpot == origin
		and move.targetSpot == expectedTarget
		for move in options
	)

	assert not any(move.ID == "ENTER" and move.originSpot == origin for move in options)

def test_seven_hop_targets_next_color():
	board = Board(COLORS)
	alice = make_player("Alice", "red", "0")

	alice.setBoard(board)

	origin = board.getSpot("red", 7)
	trigger = Move("MOVE", board.getSpot("red", 6), origin, Card("♥️", "A"), alice)

	hop = board.getSevenHopMove(trigger)

	assert hop is not None
	assert hop.originSpot is origin
	assert hop.targetSpot is board.getSpot("blue", 7)
	assert hop.player is alice
	assert hop.pieceOwner is alice

def test_seven_hop_wraps_to_first_color():
	board = Board(COLORS)
	alice = make_player("Alice", "red", "0")

	alice.setBoard(board)

	origin = board.getSpot("yellow", 7)
	trigger = Move("BACK", board.getSpot("red", 11), origin, Card("♥️", "4"), alice)

	hop = board.getSevenHopMove(trigger)

	assert hop is not None
	assert hop.targetSpot is board.getSpot("red", 7)

def test_five_hop_keeps_opponents_piece_owner():
	board = Board(COLORS)

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")

	alice.setBoard(board)
	bob.setBoard(board)

	origin = board.getSpot("red", 7)
	trigger = Move("FIVE", board.getSpot("red", 2), origin, Card("♥️", "5"), alice, bob)

	hop = board.getSevenHopMove(trigger)

	assert hop is not None
	assert hop.player is alice
	assert hop.pieceOwner is bob
	assert hop.targetSpot is board.getSpot("blue", 7)

def test_jack_switch_does_not_offer_seven_hop():
	board = Board(COLORS)

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")

	alice.setBoard(board)
	bob.setBoard(board)

	trigger = Move("SWITCH", board.getSpot("red", 2), board.getSpot("red", 7), Card("♥️", "J"), alice, bob)

	assert board.getSevenHopMove(trigger) is None

def test_backward_four_can_hop_to_previous_seven():
	rules = GameRules(seven_hopping_on_four_backward_goes_backward=True)
	board = Board(COLORS, rules)
	alice = make_player("Alice", "red", "0")
	alice.setBoard(board)

	origin = board.getSpot("red", 7)
	trigger = Move("BACK", board.getSpot("red", 11), origin, Card("♥️", "4"), alice)

	hop = board.getSevenHopMove(trigger)

	assert hop is not None
	assert hop.targetSpot is board.getSpot("yellow", 7)

def test_jack_switch_can_offer_seven_hop_when_enabled():
	rules = GameRules(jacks_can_switch_then_seven_hop=True)
	board = Board(COLORS, rules)
	alice = make_player("Alice", "red", "0")
	alice.setBoard(board)

	trigger = Move("SWITCH", board.getSpot("blue", 3), board.getSpot("yellow", 7), Card("♥️", "J"), alice)

	hop = board.getSevenHopMove(trigger)

	assert hop is not None
	assert hop.pieceOwner is alice
	assert hop.originSpot is board.getSpot("yellow", 7)
	assert hop.targetSpot is board.getSpot("red", 7)