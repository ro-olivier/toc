from cards import Card
from game import Game
from move import Move
from params import COLORS
from player import Player


def make_player(name="Alice", color="red", team="0"):
	return Player(identifier=f"TEST-{name}", name=name, team=team, color=color)


def test_apply_move_can_move_piece_between_houses():
	game = Game(None, COLORS)
	board = game.board

	player = make_player()
	player.setBoard(board)

	origin = board.getHouse("red", 0)
	target = board.getHouse("red", 2)

	origin.setOccupant(player)
	player.addAPieceOnTheBoard()

	move = Move("ENTER", origin, target, Card("♥️", "2"), player)

	game.applyMove(move)

	assert not origin.isOccupied
	assert target.isOccupied
	assert target.occupant is player
	assert player.piecesOnTheBoard == 1

def test_landing_on_own_piece_kicks_that_piece():
	game = Game(None, COLORS)
	board = game.board

	player = make_player()
	player.setBoard(board)

	origin = board.getSpot("red", 5)
	target = board.getSpot("red", 7)

	origin.setOccupant(player)
	target.setOccupant(player)

	player.addAPieceOnTheBoard()
	player.addAPieceOnTheBoard()

	move = Move("MOVE", origin, target, Card("♥️", "2"), player)

	game.applyMove(move)

	assert not origin.isOccupied
	assert target.occupant is player
	assert player.piecesOnTheBoard == 1