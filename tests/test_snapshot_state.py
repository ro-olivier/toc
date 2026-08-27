import json

import pytest
import asyncio
from datetime import timedelta, datetime, timezone

from settings import *
from toc.infrastructure.identity import createPlayerId, createResumeToken, hashResumeToken, createSessionId
from toc.infrastructure.clock import SYSTEM_CLOCK
from toc.model.cards import Card, Deck
from toc.model.player import Player
from toc.model.spot import Spot
from toc.model.move import Move
from toc.model.game import Game
from toc.model.params import COLORS
from toc.model.audit import GameEventType
from toc.model.game_phase import GamePhase
from toc.persistence.archive_store import ArchiveCategory, CompressedJsonStore
from toc.persistence.snapshot_state import CardState, DeckState, GameProgressState, GameState, PlayerGameState, PositionState, SessionSnapshotState, SevenHopProgressState, SevenSplitProgressState
from toc.persistence.finished_state import FinishedArchiveState
from main import GameSession, ConnectionManager, PlayerInputRouter

class FakeClock:
	def __init__(self, initialTime):
		self._utcNow = initialTime
		self._monotonic = 0.0

	def utcNow(self):
		return self._utcNow

	def monotonic(self):
		return self._monotonic

	def advance(self, seconds):
		self._utcNow += timedelta(seconds=seconds)
		self._monotonic += seconds

def makeGameSessionState(archiveStore=None, clock=SYSTEM_CLOCK):
	router = PlayerInputRouter()
	session = GameSession("TEST", router, clock=clock, archiveStore=archiveStore)
	playerDefinitions = [
		("Alice", "0", "red"),
		("Bob", "1", "blue"),
		("Carol", "0", "green"),
		("Diana", "1", "yellow"),
	]
	players = []

	for name, team, color in playerDefinitions:
		routerId = session.getFullPlayerId(session.id, name)
		player = Player(routerId, name, team, color, gameSession=session, router=router)
		playerId = createPlayerId()
		session.players[routerId] = {
			"name": name,
			"id": routerId,
			"playerId": playerId,
			"team": team,
			"color": color,
			"object": player,
			"configured": True,
			"resumeTokenHash": hashResumeToken(createResumeToken()),
		}
		session.order.append(routerId)
		players.append(player)

	session.game = Game(session, COLORS)
	session.game.setPlayers(players)
	return session

def makeRestorationSession(sourceSession):
	router = PlayerInputRouter()
	session = GameSession(sourceSession.id, router, sourceSession.rules, sourceSession.rulesetName)

	for sourcePlayerData in sourceSession.players.values():
		name = sourcePlayerData["name"]
		routerId = session.getFullPlayerId(session.id, name)
		player = Player(routerId, name, sourcePlayerData["team"], sourcePlayerData["color"], gameSession=session, router=router)
		session.players[routerId] = {
			"name": name,
			"id": routerId,
			"playerId": sourcePlayerData["playerId"],
			"team": sourcePlayerData["team"],
			"color": sourcePlayerData["color"],
			"object": player,
			"configured": True,
		}

	return session

def markGameAsStarted(session) -> None:
	session.markStarted()
	session.game._isStarted = True

def test_card_state_survives_json_round_trip():
	originalState = CardState.fromCard(Card("♥️", "A"))
	restoredState = CardState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.toCard() == Card("♥️", "A")


def test_deck_state_preserves_draw_and_discard_order():
	deck = Deck()
	firstCard = deck.drawCard()
	secondCard = deck.drawCard()
	deck.discardCard(firstCard)
	deck.discardCard(secondCard)

	originalState = DeckState.fromDeck(deck)
	restoredState = DeckState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.discardPile == (CardState.fromCard(firstCard), CardState.fromCard(secondCard))
	assert len(restoredState.drawPile) == 50


def test_player_game_state_preserves_hand_and_piece_count():
	player = Player("TEST-Alice", "Alice", "0", "red")
	player.hand.addToHand(Card("♠️", "5"))
	player.hand.addToHand(Card("♦️", "7"))
	player.addAPieceOnTheBoard()
	playerId = createPlayerId()

	originalState = PlayerGameState.fromPlayer(player, playerId)
	restoredState = PlayerGameState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.playerId == playerId
	assert restoredState.hand == (CardState("♠️", "5"), CardState("♦️", "7"))
	assert restoredState.piecesOnTheBoard == 1


def test_position_state_preserves_occupant_and_flags():
	player = Player("TEST-Alice", "Alice", "0", "red")
	position = Spot("yellow", 17)
	position.setOccupant(player, isOwnPlayerTakingAPieceOut=True, isBlocking=True)
	playerId = createPlayerId()

	originalState = PositionState.fromPosition(position, playerId)
	restoredState = PositionState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.positionId == "spot-yellow-17"
	assert restoredState.playerId == playerId
	assert restoredState.isBlocking
	assert restoredState.isFreshlyDeployed


def test_snapshot_state_rejects_invalid_data():
	with pytest.raises(ValueError, match="Invalid card state"):
		CardState("invalid", "A")

	with pytest.raises(ValueError, match="Invalid persistent player ID"):
		PlayerGameState("Alice", (), 0)

	with pytest.raises(ValueError, match="Invalid board-position ID"):
		PositionState("red-1", createPlayerId(), False, False)

def test_game_state_captures_complete_runtime_state():
	session = makeGameSessionState()
	game = session.game
	alice = game.players[0]

	alice.hand.addToHand(game.deck.drawCard())
	game.deck.discardCard(game.deck.drawCard())

	exitSpot = game.board.getSpot("yellow", 17)
	exitSpot.setOccupant(alice, isOwnPlayerTakingAPieceOut=True, isBlocking=True)
	alice.addAPieceOnTheBoard()

	game.resetActivePlayerIndex()
	game.advanceActivePlayer()

	originalState = GameState.fromGameSession(session)
	restoredState = GameState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.boardColors == tuple(COLORS)
	assert restoredState.activePlayerId == restoredState.playerOrder[restoredState.activePlayerIndex]
	assert restoredState.players[0].hand == (CardState.fromCard(alice.hand.cards[0]),)
	assert restoredState.positions == (
		PositionState("spot-yellow-17", restoredState.playerOrder[0], True, True),
	)
	assert len(restoredState.deck.drawPile) == 50
	assert len(restoredState.deck.discardPile) == 1


def test_game_state_rejects_missing_card():
	session = makeGameSessionState()
	payload = GameState.fromGameSession(session).to_dict()
	payload["deck"]["drawPile"].pop()

	with pytest.raises(ValueError, match="exactly 52 unique cards"):
		GameState.from_dict(payload)


def test_game_state_rejects_piece_count_mismatch():
	session = makeGameSessionState()
	alice = session.game.players[0]
	position = session.game.board.getSpot("red", 5)
	position.setOccupant(alice)
	alice.addAPieceOnTheBoard()
	payload = GameState.fromGameSession(session).to_dict()
	payload["players"][0]["piecesOnTheBoard"] = 0

	with pytest.raises(ValueError, match="piece count does not match"):
		GameState.from_dict(payload)

def test_game_state_restores_equivalent_runtime_objects():
	sourceSession = makeGameSessionState()
	sourceGame = sourceSession.game
	alice = sourceGame.players[0]

	alice.hand.addToHand(sourceGame.deck.drawCard())
	sourceGame.deck.discardCard(sourceGame.deck.drawCard())

	position = sourceGame.board.getSpot("yellow", 17)
	position.setOccupant(alice, isOwnPlayerTakingAPieceOut=True, isBlocking=True)
	alice.addAPieceOnTheBoard()

	sourceGame.resetActivePlayerIndex()
	sourceGame.advanceActivePlayer()

	originalState = GameState.fromGameSession(sourceSession)
	restoredSession = makeRestorationSession(sourceSession)
	restoredGame = originalState.restoreGame(restoredSession)
	restoredState = GameState.fromGameSession(restoredSession)

	assert restoredGame is restoredSession.game
	assert restoredGame is not sourceGame
	assert restoredState == originalState
	assert restoredGame.players[0] is not sourceGame.players[0]
	assert restoredGame.players[0].isDealer
	assert restoredGame.activePlayer is restoredGame.players[restoredGame.activePlayerIndex]
	assert restoredGame.board.getSpot("yellow", 17).occupant is restoredGame.players[0]
	assert restoredGame.board.getSpot("yellow", 17).isBlocking
	assert restoredGame.board.getSpot("yellow", 17).isFreshlyDeployed


def test_game_state_restoration_rejects_missing_session_player():
	sourceSession = makeGameSessionState()
	state = GameState.fromGameSession(sourceSession)
	restoredSession = makeRestorationSession(sourceSession)
	restoredSession.players.pop(next(iter(restoredSession.players)))

	with pytest.raises(ValueError, match="Session players do not match"):
		state.restoreGame(restoredSession)

def test_session_snapshot_survives_compressed_json_round_trip(tmp_path):
	session = makeGameSessionState()
	session.markStarted()
	session.recordEvent(GameEventType.GAME_STARTED)
	playerId = next(iter(session.players.values()))["playerId"]
	session.recordEvent(GameEventType.TURN_STARTED, playerId, {"deal": 1})

	originalState = session.snapshotState()
	store = CompressedJsonStore(tmp_path)
	store.write(ArchiveCategory.SUSPENDED, session.sessionId, originalState.to_dict())
	restoredPayload = store.read(ArchiveCategory.SUSPENDED, session.sessionId)
	restoredState = SessionSnapshotState.from_dict(restoredPayload)

	assert restoredState == originalState
	assert restoredState.metadata.sessionId == session.sessionId
	assert restoredState.game == GameState.fromGameSession(session)
	assert restoredState.events == session.events
	assert restoredState.progress == session.gameProgress


def test_session_snapshot_rejects_metadata_game_player_mismatch():
	session = makeGameSessionState()
	payload = session.snapshotState().to_dict()
	payload["metadata"]["players"].pop()

	with pytest.raises(ValueError, match="metadata and game players do not match"):
		SessionSnapshotState.from_dict(payload)

def test_seven_split_progress_survives_json_round_trip():
	actingPlayerId = createPlayerId()
	pieceOwnerId = createPlayerId()
	originalState = GameProgressState(
		phase=GamePhase.SEVEN_SPLIT,
		dealIndex=1,
		sevenSplit=SevenSplitProgressState(
			actingPlayerId=actingPlayerId,
			pieceOwnerId=pieceOwnerId,
			card=CardState("♣️", "7"),
			stepsRemaining=4,
			movedPositionIds=("spot-red-7", "house-blue-0"),
		),
	)

	restoredState = GameProgressState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.referencedPlayerIds == {actingPlayerId, pieceOwnerId}


def test_seven_hop_progress_survives_json_round_trip():
	actingPlayerId = createPlayerId()
	pieceOwnerId = createPlayerId()
	decidingPlayerId = createPlayerId()
	originalState = GameProgressState(
		phase=GamePhase.SEVEN_HOP,
		dealIndex=0,
		sevenHop=SevenHopProgressState(
			actingPlayerId=actingPlayerId,
			pieceOwnerId=pieceOwnerId,
			decidingPlayerId=decidingPlayerId,
			card=CardState("♥️", "5"),
			originPositionId="spot-red-7",
			targetPositionId="spot-blue-7",
		),
	)

	restoredState = GameProgressState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.referencedPlayerIds == {actingPlayerId, pieceOwnerId, decidingPlayerId}


def test_game_progress_rejects_phase_without_required_context():
	with pytest.raises(ValueError, match="requires seven-split progress"):
		GameProgressState(GamePhase.SEVEN_SPLIT, 0)

	with pytest.raises(ValueError, match="requires seven-hop progress"):
		GameProgressState(GamePhase.SEVEN_HOP, 0)


def test_session_snapshot_rejects_progress_for_unknown_player():
	session = makeGameSessionState()
	session.setGameProgress(GameProgressState(
		phase=GamePhase.SEVEN_SPLIT,
		dealIndex=0,
		sevenSplit=SevenSplitProgressState(
			actingPlayerId=createPlayerId(),
			pieceOwnerId=next(iter(session.players.values()))["playerId"],
			card=CardState("♠️", "7"),
			stepsRemaining=7,
		),
	))

	with pytest.raises(ValueError, match="progress references an unknown player"):
		session.snapshotState()

def test_session_records_partial_seven_split_progress():
	session = makeGameSessionState()
	alice = session.game.players[0]
	card = Card("♥️", "7")
	move = Move("SEVEN", card=card, player=alice, pieceOwner=alice)

	session.beginSevenSplit(move)
	session.updateSevenSplit(4, ("spot-red-7", "spot-blue-8"))

	progress = session.gameProgress
	aliceId = session.getPersistentPlayerId(alice)

	assert progress.phase is GamePhase.SEVEN_SPLIT
	assert progress.sevenSplit.actingPlayerId == aliceId
	assert progress.sevenSplit.pieceOwnerId == aliceId
	assert progress.sevenSplit.card == CardState("♥️", "7")
	assert progress.sevenSplit.stepsRemaining == 4
	assert progress.sevenSplit.movedPositionIds == ("spot-red-7", "spot-blue-8")


def test_session_records_pending_seven_hop_with_played_card():
	session = makeGameSessionState()
	alice = session.game.players[0]
	bob = session.game.players[1]
	origin = session.game.board.getSpot("red", 7)
	target = session.game.board.getSpot("blue", 7)
	hopMove = Move("HOP", origin, target, Card("", "1"), alice, bob)

	session.beginSevenHop(hopMove, alice, Card("♣️", "7"))

	progress = session.gameProgress

	assert progress.phase is GamePhase.SEVEN_HOP
	assert progress.sevenHop.actingPlayerId == session.getPersistentPlayerId(alice)
	assert progress.sevenHop.pieceOwnerId == session.getPersistentPlayerId(bob)
	assert progress.sevenHop.decidingPlayerId == session.getPersistentPlayerId(alice)
	assert progress.sevenHop.card == CardState("♣️", "7")
	assert progress.sevenHop.originPositionId == "spot-red-7"
	assert progress.sevenHop.targetPositionId == "spot-blue-7"

def test_complete_game_session_can_be_restored_from_snapshot():
	originalSession = makeGameSessionState()
	originalSession.markStarted()
	originalSession.recordEvent(GameEventType.GAME_STARTED)

	snapshot = SessionSnapshotState.from_dict(json.loads(json.dumps(originalSession.snapshotState().to_dict())))
	router = PlayerInputRouter()

	restoredSession = GameSession.fromSnapshot(snapshot, router)

	assert restoredSession.snapshotState() == snapshot
	assert restoredSession.sessionId == originalSession.sessionId
	assert restoredSession.joinCode == originalSession.joinCode
	assert restoredSession.rules == originalSession.rules
	assert restoredSession.rulesetName == originalSession.rulesetName
	assert restoredSession.gameTask is None

	restoredOrder = [restoredSession.players[runtimeId]["playerId"] for runtimeId in restoredSession.order]

	assert restoredOrder == list(snapshot.game.playerOrder)

def test_restored_players_start_disconnected_with_fresh_router_queues():
	originalSession = makeGameSessionState()
	snapshot = originalSession.snapshotState()
	router = PlayerInputRouter()

	restoredSession = GameSession.fromSnapshot(snapshot, router)

	for runtimeId, playerData in restoredSession.players.items():
		assert playerData["active"] is False
		assert playerData["websocket"] is None
		assert runtimeId not in router.input_queues
		assert runtimeId not in router.output_queues
		assert runtimeId in router.recycleBin
		assert runtimeId not in router.pendingPrompts

def test_session_restoration_preserves_resume_token_hashes():
	originalSession = makeGameSessionState()
	snapshot = originalSession.snapshotState()
	restoredSession = GameSession.fromSnapshot(snapshot, PlayerInputRouter())

	originalHashes = {playerData["playerId"]: playerData["resumeTokenHash"] for playerData in originalSession.players.values()}
	restoredHashes = {playerData["playerId"]: playerData["resumeTokenHash"] for playerData in restoredSession.players.values()}

	assert restoredHashes == originalHashes


def test_restored_session_resumes_partial_seven_split(monkeypatch):
	session = makeGameSessionState()
	actingPlayer = session.game.players[0]
	pieceOwner = session.game.players[0]
	positionId = str(session.game.board.positions[0])

	session.setGameProgress(GameProgressState(
		phase=GamePhase.SEVEN_SPLIT,
		dealIndex=0,
		sevenSplit=SevenSplitProgressState(
			actingPlayerId=session.getPersistentPlayerId(actingPlayer),
			pieceOwnerId=session.getPersistentPlayerId(pieceOwner),
			card=CardState("♥️", "7"),
			stepsRemaining=4,
			movedPositionIds=(positionId,),
		),
	))

	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	received = {}

	async def fakePlaySeven(player, owner, card, stepsRemaining, movedPiecePositions):
		received["player"] = player
		received["owner"] = owner
		received["card"] = card
		received["stepsRemaining"] = stepsRemaining
		received["movedPiecePositions"] = movedPiecePositions

	monkeypatch.setattr(restoredSession.game, "playSeven", fakePlaySeven)

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert received["player"] is restoredSession.getPlayerByPersistentId(session.getPersistentPlayerId(actingPlayer))
	assert received["owner"] is restoredSession.getPlayerByPersistentId(session.getPersistentPlayerId(pieceOwner))
	assert received["card"].suit == "♥️"
	assert received["card"].value == "7"
	assert received["stepsRemaining"] == 4
	assert received["movedPiecePositions"] == {restoredSession.game.board.getPositionById(positionId)}

def test_restored_session_resumes_pending_seven_hop(monkeypatch):
	session = makeGameSessionState()
	actingPlayer = session.game.players[0]
	pieceOwner = session.game.players[1]
	decidingPlayer = session.game.players[0]
	origin = session.game.board.positions[0]
	target = session.game.board.positions[1]

	session.setGameProgress(GameProgressState(
		phase=GamePhase.SEVEN_HOP,
		dealIndex=0,
		sevenHop=SevenHopProgressState(
			actingPlayerId=session.getPersistentPlayerId(actingPlayer),
			pieceOwnerId=session.getPersistentPlayerId(pieceOwner),
			decidingPlayerId=session.getPersistentPlayerId(decidingPlayer),
			card=CardState("♣️", "7"),
			originPositionId=str(origin),
			targetPositionId=str(target),
		),
	))

	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	received = {}

	async def fakeCompleteOptionalSevenHop(hopMove, player):
		received["move"] = hopMove
		received["decidingPlayer"] = player

	monkeypatch.setattr(restoredSession.game, "completeOptionalSevenHop", fakeCompleteOptionalSevenHop)

	asyncio.run(restoredSession.resumeCurrentPhase())

	hopMove = received["move"]

	assert hopMove.ID == "HOP"
	assert str(hopMove.originSpot) == str(origin)
	assert str(hopMove.targetSpot) == str(target)
	assert hopMove.card.suit == "♣️"
	assert hopMove.card.value == "7"
	assert hopMove.player is restoredSession.getPlayerByPersistentId(session.getPersistentPlayerId(actingPlayer))
	assert hopMove.pieceOwner is restoredSession.getPlayerByPersistentId(session.getPersistentPlayerId(pieceOwner))
	assert received["decidingPlayer"] is restoredSession.getPlayerByPersistentId(session.getPersistentPlayerId(decidingPlayer))

def test_turn_decision_resume_does_not_advance_active_player(monkeypatch):
	session = makeGameSessionState()
	activePlayer = session.game.advanceActivePlayer()
	activePlayerId = session.getPersistentPlayerId(activePlayer)

	session.setGameProgress(GameProgressState(GamePhase.TURN_DECISION, 0))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	restoredActivePlayer = restoredSession.getPlayerByPersistentId(activePlayerId)
	received = []

	async def fakePlayCurrentTurn():
		received.append(restoredSession.game.activePlayer)

	monkeypatch.setattr(restoredSession.game, "playCurrentTurn", fakePlayCurrentTurn)

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert received == [restoredActivePlayer]
	assert restoredSession.game.activePlayer is restoredActivePlayer

def test_turn_end_resume_only_finishes_current_turn(monkeypatch):
	session = makeGameSessionState()
	session.setGameProgress(GameProgressState(GamePhase.TURN_END, 0))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	calls = []

	async def fakeFinishCurrentTurn():
		calls.append("finish")

	async def unexpectedPlayCurrentTurn():
		raise AssertionError("TURN_END must not replay the player's turn")

	monkeypatch.setattr(restoredSession.game, "finishCurrentTurn", fakeFinishCurrentTurn)
	monkeypatch.setattr(restoredSession.game, "playCurrentTurn", unexpectedPlayCurrentTurn)

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert calls == ["finish"]

def test_card_exchange_resume_finishes_exchange_then_enters_turn_start(monkeypatch):
	session = makeGameSessionState()
	session.game._handsFinished = 0
	session.setGameProgress(GameProgressState(GamePhase.CARD_EXCHANGE, 0))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	calls = []

	async def fakeExchangeCards():
		calls.append("exchange")

	monkeypatch.setattr(restoredSession.game, "exchangeCards", fakeExchangeCards)

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert calls == ["exchange"]
	assert restoredSession.gameProgress.phase is GamePhase.TURN_START
	assert restoredSession.gameProgress.dealIndex == 0

def test_turn_start_resume_advances_to_next_player(monkeypatch):
	session = makeGameSessionState()
	session.game._handsFinished = 0
	session.setGameProgress(GameProgressState(GamePhase.TURN_START, 0))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	calls = []

	async def fakeNextPlayer():
		calls.append("next-player")

	monkeypatch.setattr(restoredSession.game, "nextPlayer", fakeNextPlayer)

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert calls == ["next-player"]

def test_turn_start_resume_enters_deal_end_when_all_hands_are_finished(monkeypatch):
	session = makeGameSessionState()
	session.game._handsFinished = session.game.numPlayers
	session.setGameProgress(GameProgressState(GamePhase.TURN_START, 0))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())

	async def unexpectedNextPlayer():
		raise AssertionError("A completed deal must not start another player turn")

	monkeypatch.setattr(restoredSession.game, "nextPlayer", unexpectedNextPlayer)

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert restoredSession.gameProgress.phase is GamePhase.DEAL_END
	assert restoredSession.gameProgress.dealIndex == 0

def test_deal_start_resume_uses_current_deal_schedule(monkeypatch):
	session = makeGameSessionState()
	session.setGameProgress(GameProgressState(GamePhase.DEAL_START, 1))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	calls = []

	async def fakeRunRound(dealNumber, cardsPerPlayer):
		calls.append((dealNumber, cardsPerPlayer))

	monkeypatch.setattr(restoredSession.game, "runRound", fakeRunRound)

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert calls == [(2, restoredSession.rules.deal_card_counts[1])]

def test_deal_end_resume_enters_next_deal():
	session = makeGameSessionState()
	session.setGameProgress(GameProgressState(GamePhase.DEAL_END, 0))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert restoredSession.gameProgress.phase is GamePhase.DEAL_START
	assert restoredSession.gameProgress.dealIndex == 1

def test_final_deal_end_resume_enters_deck_cycle_end():
	session = makeGameSessionState()
	lastDealIndex = len(session.rules.deal_card_counts) - 1
	session.setGameProgress(GameProgressState(GamePhase.DEAL_END, lastDealIndex))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert restoredSession.gameProgress.phase is GamePhase.DECK_CYCLE_END
	assert restoredSession.gameProgress.dealIndex == lastDealIndex

def test_deck_cycle_end_resume_recycles_deck_and_rotates_dealer(monkeypatch):
	session = makeGameSessionState()
	lastDealIndex = len(session.rules.deal_card_counts) - 1
	session.setGameProgress(GameProgressState(GamePhase.DECK_CYCLE_END, lastDealIndex))
	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
	calls = []

	def fakeRecycleDiscardPile(shuffle=False):
		calls.append(("recycle", shuffle))

	async def fakeNextDealer():
		calls.append(("dealer", None))

	monkeypatch.setattr(restoredSession.game.deck, "recycleDiscardPile", fakeRecycleDiscardPile)
	monkeypatch.setattr(restoredSession.game, "nextDealer", fakeNextDealer)

	expectedShuffle = restoredSession.game.shouldShuffleRecycledDeck()

	asyncio.run(restoredSession.resumeCurrentPhase())

	assert calls == [
		("recycle", expectedShuffle),
		("dealer", None),
	]
	assert restoredSession.gameProgress.phase is GamePhase.DEAL_START
	assert restoredSession.gameProgress.dealIndex == 0

def test_resumed_finished_game_is_finalised_once():
	session = makeGameSessionState()
	session.markStarted()
	session.game._isFinished = True
	session.setGameProgress(GameProgressState(GamePhase.TURN_END, 0))

	asyncio.run(session.resumeGame())
	firstEndedAt = session.endedAt

	asyncio.run(session.resumeGame())

	finishedEvents = [event for event in session.events if event.eventType is GameEventType.GAME_FINISHED]

	assert session.gameProgress.phase is GamePhase.FINISHED
	assert session.endedAt == firstEndedAt
	assert len(finishedEvents) == 1

def test_finished_phase_rejects_unfinished_game():
	session = makeGameSessionState()
	session.game._isFinished = False
	session.setGameProgress(GameProgressState(GamePhase.FINISHED, 0))

	with pytest.raises(RuntimeError, match="finished phase while its game is unfinished"):
		asyncio.run(session.resumeGame())

def test_restored_unfinished_session_waits_for_players_before_resuming():
	session = makeGameSessionState()
	markGameAsStarted(session)

	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())

	assert restoredSession.awaitingResume is True
	assert restoredSession.gameTask is None
	assert all(playerData["active"] is False for playerData in restoredSession.players.values())

def test_restored_session_does_not_resume_until_every_player_is_connected():
	async def scenario():
		session = makeGameSessionState()
		markGameAsStarted(session)
		restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())

		for playerData in list(restoredSession.players.values())[:-1]:
			playerData["active"] = True

		result = await restoredSession.start_resume_if_ready()

		assert result is False
		assert restoredSession.awaitingResume is True
		assert restoredSession.gameTask is None

	asyncio.run(scenario())

def test_fourth_reconnected_player_starts_resumed_game(monkeypatch):
	async def scenario():
		session = makeGameSessionState()
		markGameAsStarted(session)
		restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
		resumeCalls = []

		async def fakeResumedGameLoop():
			resumeCalls.append("resume")

		monkeypatch.setattr(restoredSession, "resumed_game_loop", fakeResumedGameLoop)

		for playerData in restoredSession.players.values():
			playerData["active"] = True

		result = await restoredSession.start_resume_if_ready()

		assert result is True
		assert restoredSession.awaitingResume is False
		assert restoredSession.gameTask is not None

		await restoredSession.gameTask

		assert resumeCalls == ["resume"]

	asyncio.run(scenario())

def test_simultaneous_resume_checks_start_only_one_task(monkeypatch):
	async def scenario():
		session = makeGameSessionState()
		markGameAsStarted(session)
		restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())
		resumeCalls = []

		for playerData in restoredSession.players.values():
			playerData["active"] = True

		async def fakeResumedGameLoop():
			resumeCalls.append("resume")

		monkeypatch.setattr(restoredSession, "resumed_game_loop", fakeResumedGameLoop)

		results = await asyncio.gather(
			restoredSession.start_resume_if_ready(),
			restoredSession.start_resume_if_ready(),
			restoredSession.start_resume_if_ready(),
		)

		await restoredSession.gameTask

		assert results.count(True) == 1
		assert results.count(False) == 2
		assert resumeCalls == ["resume"]

	asyncio.run(scenario())

def test_restored_finished_session_is_not_resumable():
	session = makeGameSessionState()
	markGameAsStarted(session)
	session.game._isFinished = True
	session.completeGameLifecycle()

	restoredSession = GameSession.fromSnapshot(session.snapshotState(), PlayerInputRouter())

	assert restoredSession.awaitingResume is False
	assert restoredSession.gameTask is None

def test_connection_manager_restores_suspended_game_by_join_code(tmp_path):
	session = makeGameSessionState()
	markGameAsStarted(session)
	store = CompressedJsonStore(tmp_path / "game-data")

	store.write(ArchiveCategory.SUSPENDED, session.sessionId, session.snapshotState().to_dict())

	router = PlayerInputRouter()
	manager = ConnectionManager(archiveStore=store)
	restoredSession = manager.get_or_restore_game(session.joinCode, router)

	assert restoredSession is not None
	assert restoredSession.sessionId == session.sessionId
	assert restoredSession.joinCode == session.joinCode
	assert restoredSession.awaitingResume is True
	assert manager.get_game(session.joinCode) is restoredSession
	assert all(playerData["active"] is False for playerData in restoredSession.players.values())

def test_connection_manager_returns_none_for_unknown_suspended_game(tmp_path):
	store = CompressedJsonStore(tmp_path / "game-data")
	manager = ConnectionManager(archiveStore=store)

	assert manager.get_or_restore_game("UNKNOWN", PlayerInputRouter()) is None

def test_connection_manager_does_not_reload_an_existing_live_session(tmp_path, monkeypatch):
	store = CompressedJsonStore(tmp_path / "game-data")
	manager = ConnectionManager(archiveStore=store)
	router = PlayerInputRouter()
	gameId = manager.create_game(router)

	def unexpectedList(category):
		raise AssertionError("The archive store must not be scanned for a live game")

	monkeypatch.setattr(store, "listDocumentIds", unexpectedList)

	assert manager.get_or_restore_game(gameId, router) is manager.get_game(gameId)

def test_duplicate_suspended_join_codes_are_rejected(tmp_path):
	session = makeGameSessionState()
	markGameAsStarted(session)
	store = CompressedJsonStore(tmp_path / "game-data")
	firstSnapshot = session.snapshotState().to_dict()
	secondSnapshot = session.snapshotState().to_dict()
	secondSessionId = createSessionId()

	secondSnapshot["metadata"]["sessionId"] = secondSessionId

	store.write(ArchiveCategory.SUSPENDED, session.sessionId, firstSnapshot)
	store.write(ArchiveCategory.SUSPENDED, secondSessionId, secondSnapshot)

	manager = ConnectionManager(archiveStore=store)

	with pytest.raises(RuntimeError, match="Multiple suspended archives"):
		manager.get_or_restore_game(session.joinCode, PlayerInputRouter())

def test_active_checkpoint_writes_complete_session_snapshot(tmp_path):
	store = CompressedJsonStore(tmp_path / "game-data")
	session = makeGameSessionState(store)
	markGameAsStarted(session)

	path = asyncio.run(session.checkpointActive())
	restoredPayload = store.read(ArchiveCategory.ACTIVE, session.sessionId)
	restoredSnapshot = SessionSnapshotState.from_dict(restoredPayload)

	assert path == store.pathFor(ArchiveCategory.ACTIVE, session.sessionId)
	assert restoredSnapshot == session.snapshotState()

def test_checkpoint_is_noop_without_archive_store():
	session = makeGameSessionState()
	markGameAsStarted(session)

	result = asyncio.run(session.checkpointActive())

	assert result is None

def test_restored_session_can_write_new_active_checkpoint(tmp_path):
	store = CompressedJsonStore(tmp_path / "game-data")
	session = makeGameSessionState(store)
	markGameAsStarted(session)

	store.write(ArchiveCategory.SUSPENDED, session.sessionId, session.snapshotState().to_dict())
	snapshot = SessionSnapshotState.from_dict(store.read(ArchiveCategory.SUSPENDED, session.sessionId))
	restoredSession = GameSession.fromSnapshot(snapshot, PlayerInputRouter(), archiveStore=store)

	asyncio.run(restoredSession.checkpointActive())

	assert store.read(ArchiveCategory.ACTIVE, session.sessionId) == restoredSession.snapshotState().to_dict()

def test_next_player_checkpoints_turn_decision(monkeypatch):
	async def scenario():
		session = makeGameSessionState()
		markGameAsStarted(session)
		checkpointPhases = []

		async def fakeCheckpoint():
			checkpointPhases.append(session.gameProgress.phase)

		async def fakePlayCurrentTurn():
			pass

		monkeypatch.setattr(session, "checkpointActive", fakeCheckpoint)
		monkeypatch.setattr(session.game, "playCurrentTurn", fakePlayCurrentTurn)

		await session.game.nextPlayer()

		assert checkpointPhases == [GamePhase.TURN_DECISION]
		assert session.gameProgress.phase is GamePhase.TURN_DECISION
		assert session.game.activePlayer is not None

	asyncio.run(scenario())

def test_deal_end_transition_is_checkpointed(monkeypatch):
	async def scenario():
		session = makeGameSessionState()
		markGameAsStarted(session)
		session.setGameProgress(GameProgressState(GamePhase.DEAL_END, 0))
		checkpointPhases = []

		async def fakeCheckpoint():
			checkpointPhases.append(session.gameProgress.phase)

		monkeypatch.setattr(session, "checkpointActive", fakeCheckpoint)

		await session.resumeCurrentPhase()

		assert checkpointPhases == [GamePhase.DEAL_START]
		assert session.gameProgress.dealIndex == 1

	asyncio.run(scenario())

def test_final_deal_transition_is_checkpointed(monkeypatch):
	async def scenario():
		session = makeGameSessionState()
		markGameAsStarted(session)
		lastDealIndex = len(session.rules.deal_card_counts) - 1
		session.setGameProgress(GameProgressState(GamePhase.DEAL_END, lastDealIndex))
		checkpointPhases = []

		async def fakeCheckpoint():
			checkpointPhases.append(session.gameProgress.phase)

		monkeypatch.setattr(session, "checkpointActive", fakeCheckpoint)

		await session.resumeCurrentPhase()

		assert checkpointPhases == [GamePhase.DECK_CYCLE_END]

	asyncio.run(scenario())

def test_resumed_card_exchange_checkpoints_turn_start(monkeypatch):
	async def scenario():
		session = makeGameSessionState()
		markGameAsStarted(session)
		session.setGameProgress(GameProgressState(GamePhase.CARD_EXCHANGE, 0))
		checkpointPhases = []

		async def fakeExchangeCards():
			pass

		async def fakeCheckpoint():
			checkpointPhases.append(session.gameProgress.phase)

		monkeypatch.setattr(session.game, "exchangeCards", fakeExchangeCards)
		monkeypatch.setattr(session, "checkpointActive", fakeCheckpoint)

		await session.resumeCurrentPhase()

		assert checkpointPhases == [GamePhase.TURN_START]

	asyncio.run(scenario())

def test_active_archive_can_transition_to_suspended(tmp_path):
	store = CompressedJsonStore(tmp_path / "game-data")
	session = makeGameSessionState(store)
	markGameAsStarted(session)

	asyncio.run(session.checkpointActive())

	activePath = store.pathFor(ArchiveCategory.ACTIVE, session.sessionId)
	suspendedPath = store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId)

	assert activePath.exists()
	assert not suspendedPath.exists()

	asyncio.run(session.archiveSuspended())

	assert not activePath.exists()
	assert suspendedPath.exists()
	assert session.awaitingResume is True

	restoredSnapshot = SessionSnapshotState.from_dict(store.read(ArchiveCategory.SUSPENDED, session.sessionId))

	assert restoredSnapshot == session.snapshotState()

def test_failed_suspended_write_preserves_active_archive(tmp_path, monkeypatch):
	store = CompressedJsonStore(tmp_path / "game-data")
	session = makeGameSessionState(store)
	markGameAsStarted(session)

	asyncio.run(session.checkpointActive())
	originalWrite = store.write

	def failingWrite(category, sessionId, payload):
		if category is ArchiveCategory.SUSPENDED:
			raise OSError("Simulated suspended-archive failure")

		return originalWrite(category, sessionId, payload)

	monkeypatch.setattr(store, "write", failingWrite)

	with pytest.raises(OSError, match="Simulated suspended-archive failure"):
		asyncio.run(session.archiveSuspended())

	assert store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()
	assert not store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId).exists()
	assert session.awaitingResume is False

def test_resumed_session_promotes_suspended_archive_to_active(tmp_path, monkeypatch):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)

		await session.checkpointActive()
		await session.archiveSuspended()

		snapshot = SessionSnapshotState.from_dict(store.read(ArchiveCategory.SUSPENDED, session.sessionId))
		restoredSession = GameSession.fromSnapshot(snapshot, PlayerInputRouter(), archiveStore=store)
		resumeCalls = []

		for playerData in restoredSession.players.values():
			playerData["active"] = True

		async def fakeResumedGameLoop():
			resumeCalls.append("resume")

		monkeypatch.setattr(restoredSession, "resumed_game_loop", fakeResumedGameLoop)

		assert await restoredSession.start_resume_if_ready() is True

		await restoredSession.gameTask

		assert resumeCalls == ["resume"]
		assert store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()
		assert not store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId).exists()
		assert restoredSession.awaitingResume is False

	asyncio.run(scenario())

def test_failed_active_promotion_does_not_start_resumed_game(tmp_path, monkeypatch):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)

		await session.archiveSuspended()

		snapshot = SessionSnapshotState.from_dict(store.read(ArchiveCategory.SUSPENDED, session.sessionId))
		restoredSession = GameSession.fromSnapshot(snapshot, PlayerInputRouter(), archiveStore=store)

		for playerData in restoredSession.players.values():
			playerData["active"] = True

		originalWrite = store.write

		def failingWrite(category, sessionId, payload):
			if category is ArchiveCategory.ACTIVE:
				raise OSError("Simulated active-archive failure")

			return originalWrite(category, sessionId, payload)

		monkeypatch.setattr(store, "write", failingWrite)

		with pytest.raises(OSError, match="Simulated active-archive failure"):
			await restoredSession.start_resume_if_ready()

		assert restoredSession.awaitingResume is True
		assert restoredSession.gameTask is None
		assert store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId).exists()
		assert not store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()

	asyncio.run(scenario())

def test_finished_archive_survives_json_round_trip_without_resume_tokens():
	session = makeGameSessionState()
	markGameAsStarted(session)
	session.game._isFinished = True
	session.completeGameLifecycle()

	originalState = FinishedArchiveState.fromGameSession(session)
	payload = originalState.to_dict()
	encoded = json.dumps(payload)
	restoredState = FinishedArchiveState.from_dict(json.loads(encoded))

	assert restoredState == originalState
	assert "resumeTokenHash" not in encoded
	assert "progress" not in payload
	assert payload["players"][0] == {
		"playerId": originalState.players[0].playerId,
		"name": originalState.players[0].name,
		"team": originalState.players[0].team,
		"color": originalState.players[0].color,
	}

def test_finished_archive_rejects_unfinished_game():
	session = makeGameSessionState()
	markGameAsStarted(session)

	with pytest.raises(ValueError, match="unfinished game"):
		FinishedArchiveState.fromGameSession(session)

def test_finished_archive_survives_compressed_round_trip(tmp_path):
	store = CompressedJsonStore(tmp_path / "game-data")
	session = makeGameSessionState()
	markGameAsStarted(session)
	session.game._isFinished = True
	session.completeGameLifecycle()
	originalState = FinishedArchiveState.fromGameSession(session)

	store.write(ArchiveCategory.FINISHED, session.sessionId, originalState.to_dict())

	restoredState = FinishedArchiveState.from_dict(store.read(ArchiveCategory.FINISHED, session.sessionId))

	assert restoredState == originalState

def test_finished_archive_rejects_empty_event_log():
	session = makeGameSessionState()
	markGameAsStarted(session)
	session.game._isFinished = True
	session.completeGameLifecycle()
	payload = FinishedArchiveState.fromGameSession(session).to_dict()

	payload["events"][-1]["type"] = GameEventType.TURN_STARTED.value

	with pytest.raises(ValueError, match="game-finished event"):
		FinishedArchiveState.from_dict(payload)

def test_finished_game_replaces_resumable_archives(tmp_path):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)

		await session.checkpointActive()
		store.write(ArchiveCategory.SUSPENDED, session.sessionId, session.snapshotState().to_dict())

		session.game._isFinished = True
		await session.finalizeFinishedGame()

		activePath = store.pathFor(ArchiveCategory.ACTIVE, session.sessionId)
		suspendedPath = store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId)
		finishedPath = store.pathFor(ArchiveCategory.FINISHED, session.sessionId)

		assert not activePath.exists()
		assert not suspendedPath.exists()
		assert finishedPath.exists()

		finishedState = FinishedArchiveState.from_dict(store.read(ArchiveCategory.FINISHED, session.sessionId))
		encoded = json.dumps(finishedState.to_dict())

		assert finishedState.sessionId == session.sessionId
		assert finishedState.game.isFinished is True
		assert "resumeTokenHash" not in encoded
		assert "progress" not in finishedState.to_dict()

	asyncio.run(scenario())

def test_failed_finished_write_preserves_active_archive(tmp_path, monkeypatch):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)

		await session.checkpointActive()
		originalWrite = store.write

		def failingWrite(category, sessionId, payload):
			if category is ArchiveCategory.FINISHED:
				raise OSError("Simulated finished-archive failure")

			return originalWrite(category, sessionId, payload)

		monkeypatch.setattr(store, "write", failingWrite)
		session.game._isFinished = True

		with pytest.raises(OSError, match="Simulated finished-archive failure"):
			await session.finalizeFinishedGame()

		assert store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()
		assert not store.pathFor(ArchiveCategory.FINISHED, session.sessionId).exists()

	asyncio.run(scenario())

def test_finished_game_finalization_is_idempotent(tmp_path):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)
		session.game._isFinished = True

		await session.finalizeFinishedGame()
		firstEndedAt = session.endedAt
		firstPayload = store.read(ArchiveCategory.FINISHED, session.sessionId)

		await session.finalizeFinishedGame()
		secondPayload = store.read(ArchiveCategory.FINISHED, session.sessionId)
		finishedEvents = [event for event in session.events if event.eventType is GameEventType.GAME_FINISHED]

		assert session.endedAt == firstEndedAt
		assert secondPayload == firstPayload
		assert len(finishedEvents) == 1

	asyncio.run(scenario())

def test_interrupted_active_game_is_recovered_as_suspended(tmp_path):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)
		await session.checkpointActive()

		manager = ConnectionManager(archiveStore=store)
		result = await manager.recover_interrupted_games()

		assert result == {
			"suspended": (session.sessionId,),
			"finished": (),
			"failed": (),
		}
		assert not store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()
		assert store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId).exists()

	asyncio.run(scenario())

def test_interrupted_finished_game_is_recovered_as_finished(tmp_path):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)
		session.game._isFinished = True
		await session.checkpointActive()

		manager = ConnectionManager(archiveStore=store)
		result = await manager.recover_interrupted_games()

		assert result == {
			"suspended": (),
			"finished": (session.sessionId,),
			"failed": (),
		}
		assert not store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()
		assert not store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId).exists()
		assert store.pathFor(ArchiveCategory.FINISHED, session.sessionId).exists()

		finishedState = FinishedArchiveState.from_dict(store.read(ArchiveCategory.FINISHED, session.sessionId))

		assert finishedState.game.isFinished is True
		assert finishedState.events[-1].eventType is GameEventType.GAME_FINISHED

	asyncio.run(scenario())

def test_recovery_keeps_newer_suspended_duplicate(tmp_path):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)
		activePayload = session.snapshotState().to_dict()
		suspendedPayload = session.snapshotState().to_dict()
		laterActivity = session.lastActivityAt + timedelta(seconds=30)

		suspendedPayload["metadata"]["lastActivityAt"] = laterActivity.isoformat()

		store.write(ArchiveCategory.ACTIVE, session.sessionId, activePayload)
		store.write(ArchiveCategory.SUSPENDED, session.sessionId, suspendedPayload)

		manager = ConnectionManager(archiveStore=store)
		result = await manager.recover_interrupted_games()

		assert result["suspended"] == (session.sessionId,)
		assert not store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()
		assert store.read(ArchiveCategory.SUSPENDED, session.sessionId) == suspendedPayload

	asyncio.run(scenario())

def test_recovery_prefers_active_duplicate_when_timestamps_match(tmp_path):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)
		activePayload = session.snapshotState().to_dict()
		suspendedPayload = session.snapshotState().to_dict()

		activePayload["progress"]["phase"] = GamePhase.TURN_START.value
		suspendedPayload["progress"]["phase"] = GamePhase.TURN_END.value

		store.write(ArchiveCategory.ACTIVE, session.sessionId, activePayload)
		store.write(ArchiveCategory.SUSPENDED, session.sessionId, suspendedPayload)

		manager = ConnectionManager(archiveStore=store)
		await manager.recover_interrupted_games()

		recoveredPayload = store.read(ArchiveCategory.SUSPENDED, session.sessionId)

		assert recoveredPayload["progress"]["phase"] == GamePhase.TURN_START.value
		assert not store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()

	asyncio.run(scenario())

def test_corrupt_active_archive_is_reported_without_deletion(tmp_path):
	store = CompressedJsonStore(tmp_path / "game-data")
	sessionId = createSessionId()
	path = store.pathFor(ArchiveCategory.ACTIVE, sessionId)
	path.write_bytes(b"not-a-gzip-archive")

	manager = ConnectionManager(archiveStore=store)
	result = asyncio.run(manager.recover_interrupted_games())

	assert result == {
		"suspended": (),
		"finished": (),
		"failed": (sessionId,),
	}
	assert path.exists()

def test_monitor_removes_expired_lobby_without_archiving(tmp_path):
	async def scenario():
		clock = FakeClock(datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc))
		store = CompressedJsonStore(tmp_path / "game-data")
		router = PlayerInputRouter()
		manager = ConnectionManager(clock, store)
		session = GameSession("TEST", router, clock=clock, archiveStore=store)
		manager.games[session.joinCode] = session

		clock.advance(LOBBY_LIFETIME_SECONDS)

		result = await manager.monitor_once()

		assert result == {
			"expired": ("TEST",),
			"suspended": (),
			"failed": (),
		}
		assert manager.get_game("TEST") is None
		assert store.listDocumentIds(ArchiveCategory.ACTIVE) == ()
		assert store.listDocumentIds(ArchiveCategory.SUSPENDED) == ()

	asyncio.run(scenario())

def test_monitor_suspends_game_after_disconnection_grace(tmp_path):
	async def scenario():
		clock = FakeClock(datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc))
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store, clock)
		markGameAsStarted(session)

		for playerData in session.players.values():
			playerData["active"] = False

		session.notePlayerDisconnected()
		manager = ConnectionManager(clock, store)
		manager.games[session.joinCode] = session

		clock.advance(ALL_PLAYERS_DISCONNECTED_GRACE_SECONDS)

		result = await manager.monitor_once()

		assert result == {
			"expired": (),
			"suspended": (session.joinCode,),
			"failed": (),
		}
		assert manager.get_game(session.joinCode) is None
		assert store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId).exists()
		assert not store.pathFor(ArchiveCategory.ACTIVE, session.sessionId).exists()

	asyncio.run(scenario())

def test_suspension_cancels_running_game_task(tmp_path):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)
		taskWasCancelled = asyncio.Event()

		async def waitingGameTask():
			try:
				await asyncio.Event().wait()
			finally:
				taskWasCancelled.set()

		session.gameTask = asyncio.create_task(waitingGameTask())
		await asyncio.sleep(0)

		await session.suspendGame()

		assert taskWasCancelled.is_set()
		assert session.gameTask is None
		assert session.awaitingResume is True
		assert store.pathFor(ArchiveCategory.SUSPENDED, session.sessionId).exists()

	asyncio.run(scenario())

def test_failed_suspension_restarts_cancelled_game_task(tmp_path, monkeypatch):
	async def scenario():
		store = CompressedJsonStore(tmp_path / "game-data")
		session = makeGameSessionState(store)
		markGameAsStarted(session)
		resumeStarted = asyncio.Event()

		async def waitingGameTask():
			await asyncio.Event().wait()

		async def restartedGameLoop():
			resumeStarted.set()

		async def failingArchive():
			raise OSError("Simulated suspension failure")

		session.gameTask = asyncio.create_task(waitingGameTask())
		monkeypatch.setattr(session, "archiveSuspended", failingArchive)
		monkeypatch.setattr(session, "resumed_game_loop", restartedGameLoop)

		with pytest.raises(OSError, match="Simulated suspension failure"):
			await session.suspendGame()

		await session.gameTask

		assert resumeStarted.is_set()
		assert session.awaitingResume is False

	asyncio.run(scenario())