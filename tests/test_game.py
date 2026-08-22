from toc.model.cards import Card
from toc.model.game import Game
from toc.model.move import Move
from toc.model.params import COLORS
from toc.model.player import Player
from toc.model.rules import FiveHopDecider, GameRules, MONTSURVENT_RULES, Rotation, SevenHopping, ShuffleMode
from toc.model.game_phase import GamePhase
	
import asyncio
import pytest


class FakeGameSession:
	def __init__(self):
		self.messages = []
		self.phaseChanges = []
		self.progressChanges = []
		self.dealIndex = 0
		self.checkpointCount = 0

	async def broadcast(self, message):
		self.messages.append(message)

	def setGamePhase(self, phase, dealIndex=None):
		if dealIndex is not None:
			self.dealIndex = dealIndex

		self.phaseChanges.append((phase, self.dealIndex))

	def beginSevenSplit(self, move):
		self.progressChanges.append(("seven-start", move))

	def updateSevenSplit(self, stepsRemaining, movedPositionIds=()):
		self.progressChanges.append(("seven-progress", stepsRemaining, movedPositionIds))

	def beginSevenHop(self, hopMove, decidingPlayer, playedCard=None):
		self.progressChanges.append(("seven-hop", hopMove, decidingPlayer, playedCard))

	async def checkpointActive(self):
		self.checkpointCount += 1

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

class DiscardChoosingPlayer(Player):
	def __init__(self, identifier, name, team, color, cardToDiscard):
		super().__init__(identifier, name, team, color)
		self.cardToDiscard = cardToDiscard
		self.discardPrompts = []

	async def getCardChoiceFromPlayer(self, messageKey="prompts.choose_card", fallback="What card do you want to play?"):
		self.discardPrompts.append(fallback)
		return self.cardToDiscard

	async def send_message_to_user(self, message):
		pass

class ExchangeRecordingGame(Game):
	def __init__(self, rules):
		super().__init__(FakeGameSession(), COLORS, rules)
		self.exchangeRequests = []

	async def drawHands(self, cardsPerPlayer):
		pass

	async def exchangeCards(self):
		self.exchangeRequests.extend(self.getPlayersInTeams())

	async def nextPlayer(self):
		self._handsFinished = self._numPlayers

def make_player(name="Alice", color="red", team="0"):
	return Player(identifier=f"TEST-{name}", name=name, team=team, color=color)


def place_track_piece(board, player, color, number, blocking=False):
	spot = board.getSpot(color, number)
	spot.setOccupant(player, blocking)
	player.addAPieceOnTheBoard()
	return spot

def place_house_piece(board, player, houseNumber):
	house = board.getHouse(player.color, houseNumber)
	house.setOccupant(player)
	player.addAPieceOnTheBoard()
	return house

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
	assert [change[1] for change in session.progressChanges if change[0] == "seven-progress"] == [6, 5, 4, 3, 2, 1]
	assert session.checkpointCount == 6

def test_play_seven_without_path_kicks_only_kicks_at_final_position():
	session = FakeGameSession()
	rules = GameRules(seven_split_kicks_pieces_on_path=False)
	game = Game(session, COLORS, rules)

	alice = AutomaticPlayer("TEST-Alice", "Alice", "0", "red")
	bob = Player("TEST-Bob", "Bob", "1", "blue")

	alice.setBoard(game.board)
	bob.setBoard(game.board)

	place_track_piece(game.board, alice, "red", 5)
	passedPiece = place_track_piece(game.board, bob, "red", 6)
	finalPiece = place_track_piece(game.board, bob, "red", 12)

	asyncio.run(game.playSeven(alice))

	assert passedPiece.occupant is bob
	assert finalPiece.occupant is alice
	assert bob.piecesOnTheBoard == 1

	stepMessages = [message for message in session.messages if message["type"] == "seven-step"]

	assert len(stepMessages) == 1
	assert stepMessages[0]["stepsUsed"] == 7
	assert stepMessages[0]["stepsRemaining"] == 0


def test_play_seven_without_path_kicks_resolves_each_pawns_final_position():
	session = FakeGameSession()
	rules = GameRules(seven_split_kicks_pieces_on_path=False, seven_hopping=SevenHopping.DISABLED)
	game = Game(session, COLORS, rules)

	alice = AutomaticPlayer("TEST-Alice", "Alice", "0", "red")
	bob = Player("TEST-Bob", "Bob", "1", "blue")

	alice.setBoard(game.board)
	bob.setBoard(game.board)

	place_track_piece(game.board, alice, "red", 1)
	place_track_piece(game.board, alice, "blue", 1)
	firstFinalPiece = place_track_piece(game.board, bob, "red", 2)
	passedPiece = place_track_piece(game.board, bob, "blue", 2)
	secondFinalPiece = place_track_piece(game.board, bob, "blue", 7)

	asyncio.run(game.playSeven(alice))

	assert firstFinalPiece.occupant is alice
	assert passedPiece.occupant is bob
	assert secondFinalPiece.occupant is alice
	assert bob.piecesOnTheBoard == 1

	stepMessages = [message for message in session.messages if message["type"] == "seven-step"]

	assert [message["stepsUsed"] for message in stepMessages] == [1, 6]
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

	expectedRounds = [(roundNumber, cardsPerPlayer) for roundNumber, cardsPerPlayer in enumerate(schedule, start=1)]

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

	message = session.messages[-1]

	assert message["messageKey"] == "gameplay.team_won"
	assert message["parameters"] == {"playerOne": "Alice", "playerTwo": "Bob"}
	assert message["fallback"] == "Alice and Bob win!"
	assert "msg" not in message

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
	assert session.checkpointCount == 1

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

	asyncio.run(game.runRound(1, 4))

	requestedTeams = [{player.name for player in team} for team in game.exchangeRequests]

	assert requestedTeams == [
		{"Alice", "Bob"},
		{"Carol", "Diana"},
	]
	assert game._gameSession.phaseChanges == [
		(GamePhase.DEAL_START, 0),
		(GamePhase.CARD_EXCHANGE, 0),
		(GamePhase.TURN_START, 0),
		(GamePhase.DEAL_END, 0),
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

	asyncio.run(game.runRound(1, 4))

	assert game.exchangeRequests == []
	assert (GamePhase.CARD_EXCHANGE, 0) not in game._gameSession.phaseChanges

@pytest.mark.parametrize(("shuffleMode", "expected"), [(ShuffleMode.NEVER, False), (ShuffleMode.ON_DEALER_CHANGE, True)])
def test_shuffle_decision_after_dealer_change(shuffleMode, expected):
	game = Game(FakeGameSession(), COLORS, GameRules(shuffle_cards=shuffleMode))
	game.setPlayers([
		make_player("Alice", "red", "0"),
		make_player("Bob", "blue", "1"),
		make_player("Charlie", "green", "0"),
		make_player("Diana", "yellow", "1"),
	])

	assert game.shouldShuffleRecycledDeck() is expected

@pytest.mark.parametrize("rotation", [Rotation.CLOCKWISE, Rotation.COUNTERCLOCKWISE])
def test_dealer_cycle_mode_shuffles_only_when_token_returns_to_first_dealer(rotation):
	game = Game(FakeGameSession(), COLORS, GameRules(shuffle_cards=ShuffleMode.ON_DEALER_CYCLE, rotation=rotation))
	game.setPlayers([
		make_player("Alice", "red", "0"),
		make_player("Bob", "blue", "1"),
		make_player("Charlie", "green", "0"),
		make_player("Diana", "yellow", "1"),
	])

	shuffleDecisions = []

	for _ in range(5):
		shuffleDecisions.append(game.shouldShuffleRecycledDeck())
		asyncio.run(game.nextDealer())

	assert shuffleDecisions == [False, False, False, True, False]

def test_cards_can_be_dealt_counterclockwise():
	game = Game(FakeGameSession(), COLORS, GameRules(rotation=Rotation.COUNTERCLOCKWISE))
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

	assert players[3].hand.cards == [orderedCards[0], orderedCards[4], orderedCards[8], orderedCards[12]]
	assert players[2].hand.cards == [orderedCards[1], orderedCards[5], orderedCards[9], orderedCards[13]]
	assert players[1].hand.cards == [orderedCards[2], orderedCards[6], orderedCards[10], orderedCards[14]]
	assert players[0].hand.cards == [orderedCards[3], orderedCards[7], orderedCards[11], orderedCards[15]]
	assert game.deck.size == 0

def test_players_can_take_turns_counterclockwise():
	game = Game(FakeGameSession(), COLORS, GameRules(rotation=Rotation.COUNTERCLOCKWISE))
	players = [
		make_player("Alice", "red", "0"),
		make_player("Bob", "blue", "1"),
		make_player("Charlie", "green", "0"),
		make_player("Diana", "yellow", "1"),
	]
	game.setPlayers(players)
	game.resetActivePlayerIndex()

	turnOrder = [game.advanceActivePlayer() for _ in range(4)]

	assert turnOrder == [players[3], players[2], players[1], players[0]]

def test_dealer_can_rotate_counterclockwise():
	session = FakeGameSession()
	game = Game(session, COLORS, GameRules(rotation=Rotation.COUNTERCLOCKWISE))
	players = [
		make_player("Alice", "red", "0"),
		make_player("Bob", "blue", "1"),
		make_player("Charlie", "green", "0"),
		make_player("Diana", "yellow", "1"),
	]
	game.setPlayers(players)

	asyncio.run(game.nextDealer())

	assert game.dealer is players[3]
	assert players[3].isDealer
	assert not players[0].isDealer
	assert session.messages[-1] == {"type": "dealer", "playerId": "Diana"}

def test_king_does_not_kick_crossed_pieces_when_rule_is_disabled():
	game = Game(None, COLORS, GameRules(king_kicks_pieces_on_path=False))
	board = game.board

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	alice.setBoard(board)
	bob.setBoard(board)

	origin = place_track_piece(board, alice, "red", 1)
	passedPiece = place_track_piece(board, bob, "red", 5)
	target = board.getSpotFromDistance(origin, 13)
	move = Move("MOVE", origin, target, Card("♥️", "K"), alice, alice, 13)

	game.applyMove(move)

	assert passedPiece.occupant is bob
	assert target.occupant is alice
	assert bob.piecesOnTheBoard == 1

def test_king_kicks_every_crossed_piece_when_rule_is_enabled():
	game = Game(None, COLORS, GameRules(king_kicks_pieces_on_path=True))
	board = game.board

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	partner = make_player("Partner", "green", "0")
	alice.setBoard(board)
	bob.setBoard(board)
	partner.setBoard(board)

	origin = place_track_piece(board, alice, "red", 1)
	ownedPiece = place_track_piece(board, alice, "red", 3)
	opponentPiece = place_track_piece(board, bob, "red", 5)
	partnerPiece = place_track_piece(board, partner, "red", 7)
	target = board.getSpotFromDistance(origin, 13)
	move = Move("MOVE", origin, target, Card("♥️", "K"), alice, alice, 13)

	kickedPositions = game.applyMove(move)

	assert not ownedPiece.isOccupied
	assert not opponentPiece.isOccupied
	assert not partnerPiece.isOccupied
	assert target.occupant is alice
	assert alice.piecesOnTheBoard == 1
	assert bob.piecesOnTheBoard == 0
	assert partner.piecesOnTheBoard == 0
	assert kickedPositions == [ownedPiece, opponentPiece, partnerPiece]

def test_king_cannot_cross_blocking_exit_when_path_kicking_is_enabled():
	game = Game(None, COLORS, GameRules(king_kicks_pieces_on_path=True))
	board = game.board

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	alice.setBoard(board)
	bob.setBoard(board)

	origin = place_track_piece(board, alice, "red", 10)
	place_track_piece(board, bob, "blue", 0, blocking=True)
	target = board.getSpotFromDistance(origin, 13)

	options = board.getMoveOptions(alice, Card("♥️", "K"))

	assert not any(move.ID == "MOVE" and move.originSpot == origin and move.targetSpot == target for move in options)

def test_king_cannot_kick_through_protected_house_positions():
	game = Game(None, COLORS, GameRules(king_kicks_pieces_on_path=True))
	board = game.board
	
	alice = make_player("Alice", "red", "0")
	alice.setBoard(board)

	entrySpot = board.getFirstSpot(alice.color)
	originSpot = board.getSpotFromDistance(entrySpot, -10)
	origin = place_track_piece(board, alice, originSpot.color, originSpot.number)
	place_house_piece(board, alice, 0)
	target = board.getHouse(alice.color, 2)

	options = board.getMoveOptions(alice, Card("♥️", "K"))

	assert not any(move.ID == "ENTER" and move.originSpot == origin and move.targetSpot == target for move in options)

def test_resolve_king_move_broadcasts_crossed_positions():
	session = FakeGameSession()
	game = Game(session, COLORS, GameRules(king_kicks_pieces_on_path=True, seven_hopping=SevenHopping.DISABLED))
	board = game.board

	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	alice.setBoard(board)
	bob.setBoard(board)

	origin = place_track_piece(board, alice, "red", 1)
	passedPiece = place_track_piece(board, bob, "red", 5)
	target = board.getSpotFromDistance(origin, 13)
	move = Move("MOVE", origin, target, Card("♥️", "K"), alice, alice, 13)

	asyncio.run(game.resolveMove(move))

	pathKickMessages = [message for message in session.messages if message["type"] == "path-kicks"]

	assert pathKickMessages == [{"type": "path-kicks", "positions": [str(passedPiece)]}]

def test_deployed_piece_is_blocking_when_exit_protection_is_enabled():
	game = Game(None, COLORS, GameRules(exit_spot_is_protected_and_blocking=True))
	alice = make_player("Alice", "red", "0")
	alice.setBoard(game.board)
	exitSpot = game.board.getFirstSpot(alice.color)
	move = Move("OUT", exitSpot, exitSpot, Card("♥️", "A"), alice)

	game.applyMove(move)

	assert exitSpot.isBlocking
	assert exitSpot.isFreshlyDeployed

def test_deployed_piece_is_not_blocking_when_exit_protection_is_disabled():
	game = Game(None, COLORS, GameRules(exit_spot_is_protected_and_blocking=False))
	alice = make_player("Alice", "red", "0")
	alice.setBoard(game.board)
	exitSpot = game.board.getFirstSpot(alice.color)
	move = Move("OUT", exitSpot, exitSpot, Card("♥️", "A"), alice)

	game.applyMove(move)

	assert not exitSpot.isBlocking
	assert exitSpot.isFreshlyDeployed

def test_unprotected_freshly_deployed_piece_still_cannot_enter_house():
	game = Game(None, COLORS, GameRules(exit_spot_is_protected_and_blocking=False))
	alice = make_player("Alice", "red", "0")
	alice.setBoard(game.board)
	exitSpot = game.board.getFirstSpot(alice.color)
	game.applyMove(Move("OUT", exitSpot, exitSpot, Card("♥️", "A"), alice))

	options = game.board.getMoveOptions(alice, Card("♥️", "A"))

	assert not any(move.ID == "ENTER" and move.originSpot == exitSpot for move in options)

def test_unprotected_exit_piece_can_be_kicked():
	game = Game(None, COLORS, GameRules(exit_spot_is_protected_and_blocking=False))
	board = game.board
	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	alice.setBoard(board)
	bob.setBoard(board)

	exitSpot = board.getFirstSpot(alice.color)
	game.applyMove(Move("OUT", exitSpot, exitSpot, Card("♥️", "A"), alice))
	originSpot = board.getSpotFromDistance(exitSpot, -2)
	origin = place_track_piece(board, bob, originSpot.color, originSpot.number)

	options = board.getMoveOptions(bob, Card("♥️", "2"))
	move = next(move for move in options if move.ID == "MOVE" and move.originSpot == origin and move.targetSpot == exitSpot)
	game.applyMove(move)

	assert exitSpot.occupant is bob
	assert alice.piecesOnTheBoard == 0
	assert bob.piecesOnTheBoard == 1

def test_protected_exit_piece_can_be_forced_with_five():
	game = Game(None, COLORS, GameRules(exit_spot_is_protected_and_blocking=True))
	board = game.board
	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	alice.setBoard(board)
	bob.setBoard(board)

	exitSpot = board.getFirstSpot(bob.color)
	game.applyMove(Move("OUT", exitSpot, exitSpot, Card("♥️", "A"), bob))
	target = board.getSpotFromDistance(exitSpot, 5)

	options = board.getMoveOptions(alice, Card("♥️", "5"))

	assert any(move.ID == "FIVE" and move.originSpot == exitSpot and move.targetSpot == target for move in options)

def test_protected_exit_piece_cannot_be_switched():
	game = Game(None, COLORS, GameRules(exit_spot_is_protected_and_blocking=True))
	board = game.board
	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	alice.setBoard(board)
	bob.setBoard(board)

	aliceSpot = place_track_piece(board, alice, "red", 3)
	exitSpot = board.getFirstSpot(bob.color)
	game.applyMove(Move("OUT", exitSpot, exitSpot, Card("♥️", "A"), bob))

	options = board.getMoveOptions(alice, Card("♥️", "J"))

	assert not any(move.ID == "SWITCH" and move.originSpot == aliceSpot and move.targetSpot == exitSpot for move in options)

def test_unprotected_exit_piece_can_be_switched():
	game = Game(None, COLORS, GameRules(exit_spot_is_protected_and_blocking=False))
	board = game.board
	alice = make_player("Alice", "red", "0")
	bob = make_player("Bob", "blue", "1")
	alice.setBoard(board)
	bob.setBoard(board)

	aliceSpot = place_track_piece(board, alice, "red", 3)
	exitSpot = board.getFirstSpot(bob.color)
	game.applyMove(Move("OUT", exitSpot, exitSpot, Card("♥️", "A"), bob))

	options = board.getMoveOptions(alice, Card("♥️", "J"))

	assert any(move.ID == "SWITCH" and move.originSpot == aliceSpot and move.targetSpot == exitSpot for move in options)

def test_piece_can_kick_occupied_house_when_protection_is_disabled():
	game = Game(None, COLORS, GameRules(house_spots_are_blocking_and_protected=False))
	board = game.board
	alice = make_player("Alice", "red", "0")
	alice.setBoard(board)

	origin = place_house_piece(board, alice, 0)
	occupiedTarget = place_house_piece(board, alice, 2)
	options = board.getMoveOptions(alice, Card("♥️", "2"))
	move = next(move for move in options if move.ID == "ENTER" and move.originSpot == origin and move.targetSpot == occupiedTarget)

	game.applyMove(move)

	assert not origin.isOccupied
	assert occupiedTarget.occupant is alice
	assert alice.piecesOnTheBoard == 1

def test_king_kicks_crossed_house_pieces_when_protection_is_disabled():
	rules = GameRules(king_kicks_pieces_on_path=True, house_spots_are_blocking_and_protected=False)
	game = Game(None, COLORS, rules)
	board = game.board
	alice = make_player("Alice", "red", "0")
	alice.setBoard(board)

	entrySpot = board.getFirstSpot(alice.color)
	originSpot = board.getSpotFromDistance(entrySpot, -10)
	origin = place_track_piece(board, alice, originSpot.color, originSpot.number)
	firstCrossedHouse = place_house_piece(board, alice, 0)
	secondCrossedHouse = place_house_piece(board, alice, 1)
	target = board.getHouse(alice.color, 2)

	options = board.getMoveOptions(alice, Card("♥️", "K"))
	move = next(move for move in options if move.ID == "ENTER" and move.originSpot == origin and move.targetSpot == target)

	kickedPositions = game.applyMove(move)

	assert not firstCrossedHouse.isOccupied
	assert not secondCrossedHouse.isOccupied
	assert target.occupant is alice
	assert alice.piecesOnTheBoard == 1
	assert kickedPositions == [firstCrossedHouse, secondCrossedHouse]

def test_unplayable_hand_is_folded_when_rule_is_enabled():
	session = FakeGameSession()
	game = Game(session, COLORS, GameRules(cannot_play_folds_entire_hand=True))
	alice = make_player("Alice", "red", "0")
	cardTwo = Card("♥️", "2")
	cardThree = Card("♠️", "3")
	alice.hand.addToHand(cardTwo)
	alice.hand.addToHand(cardThree)
	game.setPlayers([alice])

	asyncio.run(game.nextPlayer())

	assert alice.hand.size == 0
	assert game.deck.discardPile == [cardTwo, cardThree]
	assert game._handsFinished == 1
	assert any(message["type"] == "fold" for message in session.messages)

def test_unplayable_hand_discards_only_selected_card_when_rule_is_disabled():
	session = FakeGameSession()
	cardTwo = Card("♥️", "2")
	cardThree = Card("♠️", "3")
	alice = DiscardChoosingPlayer("TEST-Alice", "Alice", "0", "red", cardTwo)
	alice.hand.addToHand(cardTwo)
	alice.hand.addToHand(cardThree)
	game = Game(session, COLORS, GameRules(cannot_play_folds_entire_hand=False))
	game.setPlayers([alice])

	asyncio.run(game.nextPlayer())

	assert alice.hand.cards == [cardThree]
	assert game.deck.discardPile == [cardTwo]
	assert game._handsFinished == 0
	assert alice.discardPrompts == ["You cannot make a move. Choose one card to discard."]
	assert any(message["type"] == "discard" for message in session.messages)
	assert not any(message["type"] == "fold" for message in session.messages)

def test_player_can_play_on_later_turn_after_discarding_one_card():
	session = FakeGameSession()
	cardTwo = Card("♥️", "2")
	cardThree = Card("♠️", "3")
	alice = DiscardChoosingPlayer("TEST-Alice", "Alice", "0", "red", cardTwo)
	alice.hand.addToHand(cardTwo)
	alice.hand.addToHand(cardThree)
	game = Game(session, COLORS, GameRules(cannot_play_folds_entire_hand=False))
	game.setPlayers([alice])

	asyncio.run(game.nextPlayer())

	place_track_piece(game.board, alice, "red", 1)
	asyncio.run(game.nextPlayer())

	assert game.board.getSpot("red", 4).occupant is alice
	assert alice.hand.size == 0
	assert game._handsFinished == 1
	assert game.deck.discardPile == [cardTwo, cardThree]

def test_finishing_turn_recalculates_finished_hand_count():
	session = FakeGameSession()
	game = Game(session, COLORS)
	players = [
		make_player("Alice", "red", "0"),
		make_player("Bob", "blue", "1"),
		make_player("Carol", "green", "0"),
		make_player("Diana", "yellow", "1"),
	]

	game.setPlayers(players)
	game._activePlayer = players[0]
	game._activePlayerIndex = 0

	for player in players[1:]:
		player.hand.addToHand(Card("♥️", "2"))

	game._handsFinished = 3

	asyncio.run(game.finishCurrentTurn())

	assert game.handsFinished == 1

def test_all_exchange_choices_are_collected_before_hands_are_modified(monkeypatch):
	game = Game(FakeGameSession(), COLORS)
	players = [
		QuietPlayer("TEST-Alice", "Alice", "0", "red"),
		QuietPlayer("TEST-Carol", "Carol", "1", "blue"),
		QuietPlayer("TEST-Bob", "Bob", "0", "green"),
		QuietPlayer("TEST-Diana", "Diana", "1", "yellow"),
	]

	game.setPlayers(players)
	choicesCollected = []
	switchesApplied = []

	for index, player in enumerate(players):
		card = Card("♥️", str(index + 2))
		player.hand.addToHand(card)

		def makeRequestCardExchange(currentPlayer, currentCard):
			async def requestCardExchange():
				choicesCollected.append(currentPlayer.name)
				return currentCard

			return requestCardExchange

		def makeSwitchCard(currentPlayer):
			async def switchCard(givenCard, receivedCard):
				assert len(choicesCollected) == 4
				switchesApplied.append(currentPlayer.name)

			return switchCard

		monkeypatch.setattr(player, "requestCardExchange", makeRequestCardExchange(player, card))
		monkeypatch.setattr(player, "switchCard", makeSwitchCard(player))

	asyncio.run(game.exchangeCards())

	assert set(choicesCollected) == {"Alice", "Bob", "Carol", "Diana"}
	assert set(switchesApplied) == {"Alice", "Bob", "Carol", "Diana"}

def test_optional_seven_hop_checkpoints_prompt_and_result():
	session = FakeGameSession()
	game = Game(session, COLORS)
	alice = AutomaticHopPlayer("TEST-Alice", "Alice", "0", "red", False)
	alice.setBoard(game.board)

	origin = game.board.getSpot("red", 7)
	origin.setOccupant(alice)
	alice.addAPieceOnTheBoard()

	triggeringMove = Move("MOVE", game.board.getSpot("red", 5), origin, Card("♥️", "2"), alice)

	asyncio.run(game.playSevenHop(triggeringMove, triggeringMove.card))

	assert session.checkpointCount == 2