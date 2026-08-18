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

class AutomaticHopPlayer(AutomaticPlayer):
    def __init__(self, identifier, name, team, color, shouldHop):
        super().__init__(identifier, name, team, color)
        self.shouldHop = shouldHop
        self.hopRequests = []

    async def getSevenHopChoiceFromPlayer(self, originSpot, targetSpot):
        self.hopRequests.append((originSpot, targetSpot))
        return self.shouldHop

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

def test_apply_five_moves_opponent_piece_and_kicks_target():
	game = Game(None, COLORS)
	board = game.board

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")

	alice.setBoard(board)
	bob.setBoard(board)

	origin = board.getSpot("red", 5)
	target = board.getSpot("red", 10)

	origin.setOccupant(bob)
	target.setOccupant(alice)

	bob.addAPieceOnTheBoard()
	alice.addAPieceOnTheBoard()

	move = Move("FIVE", origin, target, Card("♥️", "5"), alice, bob)

	game.applyMove(move)

	assert not origin.isOccupied
	assert target.occupant is bob
	assert bob.piecesOnTheBoard == 1
	assert alice.piecesOnTheBoard == 0

def test_hop_kicks_destination_occupant():
    game = Game(None, COLORS)
    board = game.board

    alice = make_player("Alice", "red", "0")
    bob = make_player("Bob", "blue", "1")

    alice.setBoard(board)
    bob.setBoard(board)

    origin = board.getSpot("red", 7)
    target = board.getSpot("blue", 7)

    origin.setOccupant(bob)
    bob.addAPieceOnTheBoard()

    target.setOccupant(alice)
    alice.addAPieceOnTheBoard()

    hop = Move("HOP", origin, target, Card("♥️", "5"), alice, bob)
    game.applyMove(hop)

    assert not origin.isOccupied
    assert target.occupant is bob
    assert bob.piecesOnTheBoard == 1
    assert alice.piecesOnTheBoard == 0

def test_player_can_decline_seven_hop():
    session = FakeGameSession()
    game = Game(session, COLORS)
    board = game.board

    alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", False)
    alice.setBoard(board)

    origin = board.getSpot("red", 7)
    target = board.getSpot("blue", 7)

    origin.setOccupant(alice)
    alice.addAPieceOnTheBoard()

    triggeringMove = Move("MOVE", board.getSpot("red", 5), origin, Card("♥️", "2"), alice)
    result = asyncio.run(game.playSevenHop(triggeringMove))

    assert result is None
    assert origin.occupant is alice
    assert not target.isOccupied
    assert alice.hopRequests == [(origin, target)]
    assert not any(message["type"] == "seven-hop" for message in session.messages)

def test_five_player_can_accept_hop_for_opponents_piece():
    session = FakeGameSession()
    game = Game(session, COLORS)
    board = game.board

    alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", True)
    bob = make_player("Bob", "blue", "1")

    alice.setBoard(board)
    bob.setBoard(board)

    origin = board.getSpot("red", 7)
    target = board.getSpot("blue", 7)

    origin.setOccupant(bob)
    bob.addAPieceOnTheBoard()

    target.setOccupant(alice)
    alice.addAPieceOnTheBoard()

    triggeringMove = Move("FIVE", board.getSpot("red", 2), origin, Card("♥️", "5"), alice, bob)
    result = asyncio.run(game.playSevenHop(triggeringMove))

    assert result is not None
    assert alice.hopRequests == [(origin, target)]
    assert not origin.isOccupied
    assert target.occupant is bob
    assert bob.piecesOnTheBoard == 1
    assert alice.piecesOnTheBoard == 0

    hopMessages = [message for message in session.messages if message["type"] == "seven-hop"]

    assert len(hopMessages) == 1
    assert hopMessages[0]["playerId"] == "Alice"
    assert hopMessages[0]["movedPlayerId"] == "Bob"

def test_seven_split_can_hop_after_final_step():
    session = FakeGameSession()
    game = Game(session, COLORS)

    alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", True)
    alice.setBoard(game.board)

    place_track_piece(game.board, alice, "red", 0)

    asyncio.run(game.playSeven(alice))

    redSeven = game.board.getSpot("red", 7)
    blueSeven = game.board.getSpot("blue", 7)

    assert alice.hopRequests == [(redSeven, blueSeven)]
    assert not redSeven.isOccupied
    assert blueSeven.occupant is alice

    messageTypes = [message["type"] for message in session.messages]

    assert messageTypes.count("seven-step") == 7
    assert messageTypes.count("seven-hop") == 1
    assert messageTypes[-1] == "seven-hop"

def test_seven_split_cannot_hop_before_final_step():
    session = FakeGameSession()
    game = Game(session, COLORS)

    alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", True)
    alice.setBoard(game.board)

    # Step two lands on red-7, but the split eventually finishes on red-12.
    place_track_piece(game.board, alice, "red", 5)

    asyncio.run(game.playSeven(alice))

    assert alice.hopRequests == []
    assert game.board.getSpot("red", 12).occupant is alice
    assert not any(message["type"] == "seven-hop" for message in session.messages)