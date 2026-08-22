import json

import pytest

from toc.infrastructure.identity import createPlayerId, createResumeToken, hashResumeToken
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
from main import GameSession, PlayerInputRouter

def makeGameSessionState():
	router = PlayerInputRouter()
	session = GameSession("ABCDEF", router)
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