from cards import Card
from game import Game
from move import Move
from params import COLORS
from player import Player
from rules import FiveHopDecider, GameRules, MONTSURVENT_RULES, SevenHopping
	
import asyncio
import pytest


class FakeGameSession:
	def __init__(self):
		self.messages = []

	async def broadcast(self, message):
		self.messages.append(message)

class ScheduleRecordingGame(Game):
    def __init__(self, rules=MONTSURVENT_RULES):
        super().__init__(FakeGameSession(), COLORS, rules)
        self.roundCalls = []

    async def runRound(self, roundName, cardsPerPlayer):
        self.roundCalls.append((roundName, cardsPerPlayer))


class AutomaticPlayer(Player):
	async def getSevenStepChoiceFromPlayer(self, options):
		return options[0]

class WinningMovePlayer(Player):
	async def getMoveChoiceFromPlayer(self, options):
		return next(move for move in options if move.ID == "ENTER")

class AutomaticHopPlayer(AutomaticPlayer):
    def __init__(self, identifier, name, team, color, shouldHop):
        super().__init__(identifier, name, team, color)
        self.shouldHop = shouldHop
        self.hopRequests = []

    async def getSevenHopChoiceFromPlayer(self, originSpot, targetSpot):
        self.hopRequests.append((originSpot, targetSpot))
        return self.shouldHop

class QuietPlayer(Player):
    async def setHand(self, hand):
        self._hand = hand

class ExchangeRecordingGame(Game):
    def __init__(self, rules):
        super().__init__(FakeGameSession(), COLORS, rules)
        self.exchangeRequests = []

    async def drawHands(self, cardsPerPlayer):
        pass

    async def requestCardExchange(self, players):
        self.exchangeRequests.append(players)

    async def nextPlayer(self):
        self._handsFinished = self._numPlayers

def make_player(name="Alice", color="red", team="0"):
	return Player(identifier=f"TEST-{name}", name=name, team=team, color=color)


def place_track_piece(board, player, color, number):
	spot = board.getSpot(color, number)
	spot.setOccupant(player)
	player.addAPieceOnTheBoard()
	return spot

def fill_houses(board, player):
    for houseNumber in range(4):
        board.getHouse(player.color, houseNumber).setOccupant(player)
        player.addAPieceOnTheBoard()

def test_game_passes_rules_to_board():
    rules = GameRules(card_exchange=False, four_can_move_backward=False, seven_hopping=SevenHopping.DISABLED)
    game = Game(FakeGameSession(), COLORS, rules)

    assert game.rules is rules
    assert game.board.rules is rules

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

def test_cards_are_dealt_one_at_a_time_starting_after_dealer():
    game = Game(FakeGameSession(), COLORS)

    players = [
        QuietPlayer("TEST-Alice", "Alice", "0", "red"),
        QuietPlayer("TEST-Bob", "Bob", "1", "blue"),
        QuietPlayer("TEST-Charlie", "Charlie", "0", "green"),
        QuietPlayer("TEST-Diana", "Diana", "1", "yellow"),
    ]

    game.setPlayers(players)

    orderedCards = [Card("", str(index)) for index in range(16)]
    game.deck._cards = orderedCards.copy()

    asyncio.run(game.drawHands(4))

    assert players[1].hand.cards == [orderedCards[0], orderedCards[4], orderedCards[8], orderedCards[12]]
    assert players[2].hand.cards == [orderedCards[1], orderedCards[5], orderedCards[9], orderedCards[13]]
    assert players[3].hand.cards == [orderedCards[2], orderedCards[6], orderedCards[10], orderedCards[14]]
    assert players[0].hand.cards == [orderedCards[3], orderedCards[7], orderedCards[11], orderedCards[15]]
    assert game.deck.size == 0

def test_player_after_dealer_plays_first():
    game = Game(FakeGameSession(), COLORS)

    players = [
        make_player("Alice", "red", "0"),
        make_player("Bob", "blue", "1"),
        make_player("Charlie", "green", "0"),
        make_player("Diana", "yellow", "1"),
    ]

    game.setPlayers(players)
    game.resetActivePlayerIndex()

    assert game.advanceActivePlayer() is players[1]

def test_dealer_rotates_clockwise():
    session = FakeGameSession()
    game = Game(session, COLORS)

    players = [
        make_player("Alice", "red", "0"),
        make_player("Bob", "blue", "1"),
        make_player("Charlie", "green", "0"),
        make_player("Diana", "yellow", "1"),
    ]

    game.setPlayers(players)

    assert game.dealer is players[0]
    assert players[0].isDealer

    asyncio.run(game.nextDealer())

    assert game.dealer is players[1]
    assert players[1].isDealer
    assert not players[0].isDealer
    assert session.messages[-1] == {"type": "dealer", "playerId": "Bob"}

@pytest.mark.parametrize("schedule", [(5, 4, 4), (4, 5, 4), (4, 4, 5)])
def test_deck_cycle_uses_configured_deal_schedule(schedule):
    rules = GameRules(deal_card_counts=schedule)
    game = ScheduleRecordingGame(rules)

    asyncio.run(game.runDeckCycle())

    expectedRounds = [(f"Deal {roundNumber}", cardsPerPlayer) for roundNumber, cardsPerPlayer in enumerate(schedule, start=1)]

    assert game.roundCalls == expectedRounds

def test_finished_player_controls_teammate_without_changing_color():
    game = Game(FakeGameSession(), COLORS)

    alice = make_player("Alice", "red", "0")
    bob = make_player("Bob", "blue", "0")
    carol = make_player("Carol", "green", "1")
    diana = make_player("Diana", "yellow", "1")

    game.setPlayers([alice, carol, bob, diana])
    fill_houses(game.board, alice)

    assert game.getControlledPlayer(alice) is bob
    assert alice.color == "red"

def test_finished_player_moves_teammates_piece():
    game = Game(FakeGameSession(), COLORS)

    alice = make_player("Alice", "red", "0")
    bob = make_player("Bob", "blue", "0")
    carol = make_player("Carol", "green", "1")
    diana = make_player("Diana", "yellow", "1")

    game.setPlayers([alice, carol, bob, diana])
    fill_houses(game.board, alice)

    origin = place_track_piece(game.board, bob, "red", 5)
    options = game.board.getMoveOptions(alice, Card("♥️", "2"), bob)
    move = next(move for move in options if move.ID == "MOVE" and move.originSpot is origin)

    assert move.player is alice
    assert move.pieceOwner is bob

    game.applyMove(move)

    assert move.targetSpot.occupant is bob
    assert alice.color == "red"

def test_finished_player_can_play_seven_for_teammate():
    session = FakeGameSession()
    game = Game(session, COLORS)

    alice = AutomaticPlayer("TEST-Alice", "Alice", "0", "red")
    bob = make_player("Bob", "blue", "0")
    carol = make_player("Carol", "green", "1")
    diana = make_player("Diana", "yellow", "1")

    game.setPlayers([alice, carol, bob, diana])
    fill_houses(game.board, alice)
    place_track_piece(game.board, bob, "red", 5)

    asyncio.run(game.playSeven(alice, bob))

    assert game.board.getSpot("red", 12).occupant is bob

    stepMessages = [message for message in session.messages if message["type"] == "seven-step"]

    assert len(stepMessages) == 7
    assert all(message["movedPlayerId"] == "Bob" for message in stepMessages)

def test_team_wins_when_both_house_lanes_are_full():
    session = FakeGameSession()
    game = Game(session, COLORS)

    alice = make_player("Alice", "red", "0")
    bob = make_player("Bob", "blue", "0")
    carol = make_player("Carol", "green", "1")
    diana = make_player("Diana", "yellow", "1")

    game.setPlayers([alice, carol, bob, diana])
    fill_houses(game.board, alice)
    fill_houses(game.board, bob)

    result = asyncio.run(game.finishGameIfWon())

    assert result is True
    assert game.isFinished
    assert session.messages[-1]["type"] == "game-over"
    assert session.messages[-1]["winners"] == ["Alice", "Bob"]

def test_ordinary_turn_finishing_team_triggers_victory_immediately():
	session = FakeGameSession()
	game = Game(session, COLORS)
	alice = WinningMovePlayer("TEST-Alice", "Alice", "0", "red")
	bob = make_player("Bob", "blue", "0")
	carol = make_player("Carol", "green", "1")
	diana = make_player("Diana", "yellow", "1")
	game.setPlayers([alice, carol, bob, diana])

	fill_houses(game.board, alice)
	for houseNumber in range(1, 4):
		game.board.getHouse("blue", houseNumber).setOccupant(bob)
		bob.addAPieceOnTheBoard()
	entrySpot = game.board.getFirstSpot("blue")
	entrySpot.setOccupant(bob)
	bob.addAPieceOnTheBoard()
	alice.hand.addToHand(Card("♥️", "A"))

	asyncio.run(game.nextPlayer())

	assert game.board.getHouse("blue", 0).occupant is bob
	assert game.isFinished
	gameOverMessages = [message for message in session.messages if message["type"] == "game-over"]
	assert len(gameOverMessages) == 1
	assert gameOverMessages[0]["winners"] == ["Alice", "Bob"]

def test_seven_hop_is_not_offered_when_disabled():
    session = FakeGameSession()
    rules = GameRules(seven_hopping=SevenHopping.DISABLED)
    game = Game(session, COLORS, rules)
    alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", True)
    alice.setBoard(game.board)

    origin = game.board.getSpot("red", 7)
    target = game.board.getSpot("blue", 7)
    origin.setOccupant(alice)
    alice.addAPieceOnTheBoard()

    triggeringMove = Move("MOVE", game.board.getSpot("red", 5), origin, Card("♥️", "2"), alice)
    result = asyncio.run(game.playSevenHop(triggeringMove))

    assert result is None
    assert origin.occupant is alice
    assert not target.isOccupied
    assert alice.hopRequests == []

def test_seven_hop_is_applied_without_prompt_when_forced():
    session = FakeGameSession()
    rules = GameRules(seven_hopping=SevenHopping.FORCED)
    game = Game(session, COLORS, rules)
    alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", False)
    alice.setBoard(game.board)

    origin = game.board.getSpot("red", 7)
    target = game.board.getSpot("blue", 7)
    origin.setOccupant(alice)
    alice.addAPieceOnTheBoard()

    triggeringMove = Move("MOVE", game.board.getSpot("red", 5), origin, Card("♥️", "2"), alice)
    result = asyncio.run(game.playSevenHop(triggeringMove))

    assert result is not None
    assert not origin.isOccupied
    assert target.occupant is alice
    assert alice.hopRequests == []

def test_piece_owner_decides_optional_five_hop_when_configured():
    session = FakeGameSession()
    rules = GameRules(five_hop_decider=FiveHopDecider.PIECE_OWNER)
    game = Game(session, COLORS, rules)
    alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", False)
    bob = AutomaticHopPlayer("TEST-Bob", "Bob", "1", "blue", True)

    alice.setBoard(game.board)
    bob.setBoard(game.board)

    origin = game.board.getSpot("red", 7)
    target = game.board.getSpot("blue", 7)
    origin.setOccupant(bob)
    bob.addAPieceOnTheBoard()

    triggeringMove = Move("FIVE", game.board.getSpot("red", 2), origin, Card("♥️", "5"), alice, bob)
    result = asyncio.run(game.playSevenHop(triggeringMove))

    assert result is not None
    assert alice.hopRequests == []
    assert bob.hopRequests == [(origin, target)]
    assert target.occupant is bob

def test_round_requests_card_exchange_for_each_team_when_enabled():
    game = ExchangeRecordingGame(GameRules(card_exchange=True))
    players = [
        make_player("Alice", "red", "0"),
        make_player("Carol", "green", "1"),
        make_player("Bob", "blue", "0"),
        make_player("Diana", "yellow", "1"),
    ]
    game.setPlayers(players)

    asyncio.run(game.runRound("Test round", 4))

    requestedTeams = [{player.name for player in team} for team in game.exchangeRequests]

    assert requestedTeams == [
        {"Alice", "Bob"},
        {"Carol", "Diana"},
    ]

def test_round_skips_card_exchange_when_disabled():
    game = ExchangeRecordingGame(GameRules(card_exchange=False))
    players = [
        make_player("Alice", "red", "0"),
        make_player("Carol", "green", "1"),
        make_player("Bob", "blue", "0"),
        make_player("Diana", "yellow", "1"),
    ]
    game.setPlayers(players)

    asyncio.run(game.runRound("Test round", 4))

    assert game.exchangeRequests == []