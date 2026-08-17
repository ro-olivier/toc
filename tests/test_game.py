from cards import Card
from game import Game
from move import Move
from params import COLORS
from player import Player
    
import asyncio


class FakeGameSession:
    def __init__(self):
        self.messages = []

    async def broadcast(self, message):
        self.messages.append(message)


class AutomaticPlayer(Player):
    async def getSevenStepChoiceFromPlayer(self, options):
        return options[0]

def make_player(name="Alice", color="red", team="0"):
    return Player(identifier=f"TEST-{name}", name=name, team=team, color=color)


def place_track_piece(board, player, color, number):
    spot = board.getSpot(color, number)
    spot.setOccupant(player)
    player.addAPieceOnTheBoard()
    return spot


def test_play_seven_moves_exactly_seven_steps():
    session = FakeGameSession()
    game = Game(session, COLORS)

    alice = AutomaticPlayer("TEST-Alice", "Alice", "0", "red")
    alice.setBoard(game.board)

    place_track_piece(game.board, alice, "red", 5)

    asyncio.run(game.playSeven(alice))

    assert game.board.getSpot("red", 12).occupant is alice
    assert alice.piecesOnTheBoard == 1

    stepMessages = [message for message in session.messages if message["type"] == "seven-step"]

    assert len(stepMessages) == 7
    assert stepMessages[-1]["stepsRemaining"] == 0


def test_play_seven_kicks_after_each_step():
    session = FakeGameSession()
    game = Game(session, COLORS)

    alice = AutomaticPlayer("TEST-Alice", "Alice", "0", "red")
    bob = Player("TEST-Bob", "Bob", "1", "blue")

    alice.setBoard(game.board)
    bob.setBoard(game.board)

    place_track_piece(game.board, alice, "red", 5)
    place_track_piece(game.board, bob, "red", 6)
    place_track_piece(game.board, bob, "red", 7)

    asyncio.run(game.playSeven(alice))

    assert bob.piecesOnTheBoard == 0
    assert game.board.getSpot("red", 12).occupant is alice


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