from dataclasses import dataclass
from uuid import UUID

from toc.model.cards import Card, Deck
from toc.model.params import SPOTS_PER_HOUSE, SUITS, VALUES
from toc.model.game import Game
from toc.model.audit import GameEvent
from toc.model.game_phase import GamePhase
from toc.persistence.persistent_state import SessionMetadataState


def _validatePlayerId(playerId: str) -> None:
	if type(playerId) is not str:
		raise ValueError("Invalid persistent player ID")

	try:
		if UUID(hex=playerId).hex != playerId:
			raise ValueError
	except ValueError as error:
		raise ValueError("Invalid persistent player ID") from error

def _validatePositionId(positionId: str) -> None:
	positionParts = positionId.split("-") if type(positionId) is str else []

	if len(positionParts) != 3 or positionParts[0] not in ("spot", "house") or not positionParts[1]:
		raise ValueError("Invalid board-position ID")

	try:
		positionNumber = int(positionParts[2])
	except ValueError as error:
		raise ValueError("Invalid board-position ID") from error

	if positionNumber < 0 or str(positionNumber) != positionParts[2]:
		raise ValueError("Invalid board-position ID")

@dataclass(frozen=True, slots=True)
class CardState:
	suit: str
	value: str

	def __post_init__(self) -> None:
		if self.suit not in SUITS or self.value not in VALUES:
			raise ValueError("Invalid card state")

	def to_dict(self) -> dict:
		return {"suit": self.suit, "value": self.value}

	@classmethod
	def from_dict(cls, values: dict) -> "CardState":
		if type(values) is not dict or set(values) != {"suit", "value"}:
			raise ValueError("Invalid card state")

		return cls(suit=values["suit"], value=values["value"])

	@classmethod
	def fromCard(cls, card: Card) -> "CardState":
		return cls(suit=card.suit, value=card.value)

	def toCard(self, deck: Deck = None) -> Card:
		return Card(self.suit, self.value, deck)


@dataclass(frozen=True, slots=True)
class DeckState:
	drawPile: tuple[CardState, ...]
	discardPile: tuple[CardState, ...]

	def __post_init__(self) -> None:
		if type(self.drawPile) is not tuple or type(self.discardPile) is not tuple:
			raise ValueError("Deck-state piles must be tuples")

		if not all(isinstance(card, CardState) for card in self.drawPile + self.discardPile):
			raise ValueError("Invalid card in deck state")

	def to_dict(self) -> dict:
		return {
			"drawPile": [card.to_dict() for card in self.drawPile],
			"discardPile": [card.to_dict() for card in self.discardPile],
		}

	@classmethod
	def from_dict(cls, values: dict) -> "DeckState":
		if type(values) is not dict or set(values) != {"drawPile", "discardPile"}:
			raise ValueError("Invalid deck state")

		if type(values["drawPile"]) is not list or type(values["discardPile"]) is not list:
			raise ValueError("Invalid deck-state piles")

		return cls(
			drawPile=tuple(CardState.from_dict(card) for card in values["drawPile"]),
			discardPile=tuple(CardState.from_dict(card) for card in values["discardPile"]),
		)

	@classmethod
	def fromDeck(cls, deck: Deck) -> "DeckState":
		return cls(
			drawPile=tuple(CardState.fromCard(card) for card in deck.cards),
			discardPile=tuple(CardState.fromCard(card) for card in deck.discardPile),
		)


@dataclass(frozen=True, slots=True)
class PlayerGameState:
	playerId: str
	hand: tuple[CardState, ...]
	piecesOnTheBoard: int

	def __post_init__(self) -> None:
		_validatePlayerId(self.playerId)

		if type(self.hand) is not tuple or not all(isinstance(card, CardState) for card in self.hand):
			raise ValueError("Invalid player hand state")

		if type(self.piecesOnTheBoard) is not int or not 0 <= self.piecesOnTheBoard <= SPOTS_PER_HOUSE:
			raise ValueError("Invalid player piece count")

	def to_dict(self) -> dict:
		return {
			"playerId": self.playerId,
			"hand": [card.to_dict() for card in self.hand],
			"piecesOnTheBoard": self.piecesOnTheBoard,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "PlayerGameState":
		if type(values) is not dict or set(values) != {"playerId", "hand", "piecesOnTheBoard"}:
			raise ValueError("Invalid player game state")

		if type(values["hand"]) is not list:
			raise ValueError("Invalid player hand state")

		return cls(
			playerId=values["playerId"],
			hand=tuple(CardState.from_dict(card) for card in values["hand"]),
			piecesOnTheBoard=values["piecesOnTheBoard"],
		)

	@classmethod
	def fromPlayer(cls, player, playerId: str) -> "PlayerGameState":
		return cls(
			playerId=playerId,
			hand=tuple(CardState.fromCard(card) for card in player.hand.cards),
			piecesOnTheBoard=player.piecesOnTheBoard,
		)


@dataclass(frozen=True, slots=True)
class PositionState:
	positionId: str
	playerId: str
	isBlocking: bool
	isFreshlyDeployed: bool

	def __post_init__(self) -> None:
		positionParts = self.positionId.split("-") if type(self.positionId) is str else []

		if len(positionParts) != 3 or positionParts[0] not in ("spot", "house") or not positionParts[1]:
			raise ValueError("Invalid board-position ID")

		try:
			positionNumber = int(positionParts[2])
		except ValueError as error:
			raise ValueError("Invalid board-position ID") from error

		if positionNumber < 0 or str(positionNumber) != positionParts[2]:
			raise ValueError("Invalid board-position ID")

		_validatePositionId(self.positionId)
		_validatePlayerId(self.playerId)

		if type(self.isBlocking) is not bool or type(self.isFreshlyDeployed) is not bool:
			raise ValueError("Invalid board-position flags")

	def to_dict(self) -> dict:
		return {
			"positionId": self.positionId,
			"playerId": self.playerId,
			"isBlocking": self.isBlocking,
			"isFreshlyDeployed": self.isFreshlyDeployed,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "PositionState":
		expectedFields = {"positionId", "playerId", "isBlocking", "isFreshlyDeployed"}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid board-position state")

		return cls(
			positionId=values["positionId"],
			playerId=values["playerId"],
			isBlocking=values["isBlocking"],
			isFreshlyDeployed=values["isFreshlyDeployed"],
		)

	@classmethod
	def fromPosition(cls, position, playerId: str) -> "PositionState":
		if not position.isOccupied:
			raise ValueError("Cannot serialize an unoccupied board position")

		return cls(
			positionId=str(position),
			playerId=playerId,
			isBlocking=position.isBlocking,
			isFreshlyDeployed=position.isFreshlyDeployed,
		)


@dataclass(frozen=True, slots=True)
class SevenSplitProgressState:
	actingPlayerId: str
	pieceOwnerId: str
	card: CardState
	stepsRemaining: int
	movedPositionIds: tuple[str, ...] = ()

	def __post_init__(self) -> None:
		_validatePlayerId(self.actingPlayerId)
		_validatePlayerId(self.pieceOwnerId)

		if not isinstance(self.card, CardState) or self.card.value != "7":
			raise ValueError("Seven-split progress requires a seven")

		if type(self.stepsRemaining) is not int or not 1 <= self.stepsRemaining <= 7:
			raise ValueError("Invalid remaining seven-split steps")

		if type(self.movedPositionIds) is not tuple:
			raise ValueError("Invalid moved-position list")

		for positionId in self.movedPositionIds:
			_validatePositionId(positionId)

		if len(set(self.movedPositionIds)) != len(self.movedPositionIds):
			raise ValueError("Seven-split progress contains duplicate moved positions")

	def to_dict(self) -> dict:
		return {
			"actingPlayerId": self.actingPlayerId,
			"pieceOwnerId": self.pieceOwnerId,
			"card": self.card.to_dict(),
			"stepsRemaining": self.stepsRemaining,
			"movedPositionIds": list(self.movedPositionIds),
		}

	@classmethod
	def from_dict(cls, values: dict) -> "SevenSplitProgressState":
		expectedFields = {"actingPlayerId", "pieceOwnerId", "card", "stepsRemaining", "movedPositionIds"}

		if type(values) is not dict or set(values) != expectedFields or type(values["movedPositionIds"]) is not list:
			raise ValueError("Invalid seven-split progress")

		return cls(
			actingPlayerId=values["actingPlayerId"],
			pieceOwnerId=values["pieceOwnerId"],
			card=CardState.from_dict(values["card"]),
			stepsRemaining=values["stepsRemaining"],
			movedPositionIds=tuple(values["movedPositionIds"]),
		)


@dataclass(frozen=True, slots=True)
class SevenHopProgressState:
	actingPlayerId: str
	pieceOwnerId: str
	decidingPlayerId: str
	card: CardState
	originPositionId: str
	targetPositionId: str

	def __post_init__(self) -> None:
		_validatePlayerId(self.actingPlayerId)
		_validatePlayerId(self.pieceOwnerId)
		_validatePlayerId(self.decidingPlayerId)

		if not isinstance(self.card, CardState):
			raise ValueError("Invalid seven-hop card")

		_validatePositionId(self.originPositionId)
		_validatePositionId(self.targetPositionId)

	def to_dict(self) -> dict:
		return {
			"actingPlayerId": self.actingPlayerId,
			"pieceOwnerId": self.pieceOwnerId,
			"decidingPlayerId": self.decidingPlayerId,
			"card": self.card.to_dict(),
			"originPositionId": self.originPositionId,
			"targetPositionId": self.targetPositionId,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "SevenHopProgressState":
		expectedFields = {"actingPlayerId", "pieceOwnerId", "decidingPlayerId", "card", "originPositionId", "targetPositionId"}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid seven-hop progress")

		return cls(
			actingPlayerId=values["actingPlayerId"],
			pieceOwnerId=values["pieceOwnerId"],
			decidingPlayerId=values["decidingPlayerId"],
			card=CardState.from_dict(values["card"]),
			originPositionId=values["originPositionId"],
			targetPositionId=values["targetPositionId"],
		)


@dataclass(frozen=True, slots=True)
class GameProgressState:
	phase: GamePhase
	dealIndex: int
	sevenSplit: SevenSplitProgressState | None = None
	sevenHop: SevenHopProgressState | None = None

	def __post_init__(self) -> None:
		if not isinstance(self.phase, GamePhase):
			raise ValueError("Invalid game phase")

		if type(self.dealIndex) is not int or self.dealIndex < 0:
			raise ValueError("Invalid deal index")

		if self.phase is GamePhase.SEVEN_SPLIT:
			if not isinstance(self.sevenSplit, SevenSplitProgressState) or self.sevenHop is not None:
				raise ValueError("Seven-split phase requires seven-split progress")

		elif self.phase is GamePhase.SEVEN_HOP:
			if not isinstance(self.sevenHop, SevenHopProgressState) or self.sevenSplit is not None:
				raise ValueError("Seven-hop phase requires seven-hop progress")

		elif self.sevenSplit is not None or self.sevenHop is not None:
			raise ValueError("Current game phase cannot contain seven progress")

	@property
	def referencedPlayerIds(self) -> set[str]:
		if self.sevenSplit is not None:
			return {self.sevenSplit.actingPlayerId, self.sevenSplit.pieceOwnerId}

		if self.sevenHop is not None:
			return {
				self.sevenHop.actingPlayerId,
				self.sevenHop.pieceOwnerId,
				self.sevenHop.decidingPlayerId,
			}

		return set()

	def to_dict(self) -> dict:
		return {
			"phase": self.phase.value,
			"dealIndex": self.dealIndex,
			"sevenSplit": self.sevenSplit.to_dict() if self.sevenSplit is not None else None,
			"sevenHop": self.sevenHop.to_dict() if self.sevenHop is not None else None,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "GameProgressState":
		if type(values) is not dict or set(values) != {"phase", "dealIndex", "sevenSplit", "sevenHop"}:
			raise ValueError("Invalid game progress")

		try:
			phase = GamePhase(values["phase"])
		except (TypeError, ValueError) as error:
			raise ValueError("Invalid game phase") from error

		return cls(
			phase=phase,
			dealIndex=values["dealIndex"],
			sevenSplit=SevenSplitProgressState.from_dict(values["sevenSplit"]) if values["sevenSplit"] is not None else None,
			sevenHop=SevenHopProgressState.from_dict(values["sevenHop"]) if values["sevenHop"] is not None else None,
		)


@dataclass(frozen=True, slots=True)
class GameState:
	isStarted: bool
	isFinished: bool
	handsFinished: int
	activePlayerIndex: int
	activePlayerId: str | None
	dealerRotationCount: int
	boardColors: tuple[str, ...]
	playerOrder: tuple[str, ...]
	players: tuple[PlayerGameState, ...]
	positions: tuple[PositionState, ...]
	deck: DeckState

	def __post_init__(self) -> None:
		if type(self.isStarted) is not bool or type(self.isFinished) is not bool:
			raise ValueError("Invalid game status")

		if type(self.playerOrder) is not tuple or not self.playerOrder:
			raise ValueError("Invalid player order")

		for playerId in self.playerOrder:
			_validatePlayerId(playerId)

		if len(set(self.playerOrder)) != len(self.playerOrder):
			raise ValueError("Player order contains duplicate IDs")

		if type(self.boardColors) is not tuple or len(self.boardColors) != len(self.playerOrder):
			raise ValueError("Invalid board colours")

		if any(type(color) is not str or not color for color in self.boardColors) or len(set(self.boardColors)) != len(self.boardColors):
			raise ValueError("Invalid board colours")

		if type(self.players) is not tuple or not all(isinstance(player, PlayerGameState) for player in self.players):
			raise ValueError("Invalid player game states")

		playerIds = tuple(player.playerId for player in self.players)

		if playerIds != self.playerOrder:
			raise ValueError("Player game states do not match player order")

		if type(self.handsFinished) is not int or not 0 <= self.handsFinished <= len(self.players):
			raise ValueError("Invalid finished-hand count")

		if type(self.activePlayerIndex) is not int or not -1 <= self.activePlayerIndex < len(self.players):
			raise ValueError("Invalid active-player index")

		if self.activePlayerId is not None:
			_validatePlayerId(self.activePlayerId)

			if self.activePlayerIndex < 0 or self.playerOrder[self.activePlayerIndex] != self.activePlayerId:
				raise ValueError("Active player does not match active-player index")

		if type(self.dealerRotationCount) is not int or self.dealerRotationCount < 0:
			raise ValueError("Invalid dealer rotation count")

		if type(self.positions) is not tuple or not all(isinstance(position, PositionState) for position in self.positions):
			raise ValueError("Invalid board positions")

		positionIds = [position.positionId for position in self.positions]

		if len(set(positionIds)) != len(positionIds):
			raise ValueError("Board state contains duplicate positions")

		if any(position.playerId not in self.playerOrder for position in self.positions):
			raise ValueError("Board state contains an unknown player")

		if not isinstance(self.deck, DeckState):
			raise ValueError("Invalid deck state")

		allCards = list(self.deck.drawPile) + list(self.deck.discardPile)

		for player in self.players:
			allCards.extend(player.hand)

		expectedCardCount = len(SUITS) * len(VALUES)

		if len(allCards) != expectedCardCount or len(set(allCards)) != expectedCardCount:
			raise ValueError("Game state must contain exactly 52 unique cards")

		pieceCounts = {playerId: 0 for playerId in self.playerOrder}

		for position in self.positions:
			pieceCounts[position.playerId] += 1

		for player in self.players:
			if pieceCounts[player.playerId] != player.piecesOnTheBoard:
				raise ValueError("Player piece count does not match board state")

	def to_dict(self) -> dict:
		return {
			"isStarted": self.isStarted,
			"isFinished": self.isFinished,
			"handsFinished": self.handsFinished,
			"activePlayerIndex": self.activePlayerIndex,
			"activePlayerId": self.activePlayerId,
			"dealerRotationCount": self.dealerRotationCount,
			"boardColors": list(self.boardColors),
			"playerOrder": list(self.playerOrder),
			"players": [player.to_dict() for player in self.players],
			"positions": [position.to_dict() for position in self.positions],
			"deck": self.deck.to_dict(),
		}

	@classmethod
	def from_dict(cls, values: dict) -> "GameState":
		expectedFields = {
			"isStarted", "isFinished", "handsFinished", "activePlayerIndex",
			"activePlayerId", "dealerRotationCount", "boardColors", "playerOrder",
			"players", "positions", "deck",
		}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid game state")

		for fieldName in ("boardColors", "playerOrder", "players", "positions"):
			if type(values[fieldName]) is not list:
				raise ValueError(f"Invalid game-state field: {fieldName}")

		return cls(
			isStarted=values["isStarted"],
			isFinished=values["isFinished"],
			handsFinished=values["handsFinished"],
			activePlayerIndex=values["activePlayerIndex"],
			activePlayerId=values["activePlayerId"],
			dealerRotationCount=values["dealerRotationCount"],
			boardColors=tuple(values["boardColors"]),
			playerOrder=tuple(values["playerOrder"]),
			players=tuple(PlayerGameState.from_dict(player) for player in values["players"]),
			positions=tuple(PositionState.from_dict(position) for position in values["positions"]),
			deck=DeckState.from_dict(values["deck"]),
		)

	@classmethod
	def fromGameSession(cls, session) -> "GameState":
		if session.game is None:
			raise ValueError("Cannot snapshot a session without a game")

		game = session.game
		playerDataByObject = {playerData["object"]: playerData for playerData in session.players.values()}

		try:
			playerOrder = tuple(playerDataByObject[player]["playerId"] for player in game.players)
		except KeyError as error:
			raise ValueError("Game contains a player without persistent metadata") from error

		players = tuple(PlayerGameState.fromPlayer(player, playerId) for player, playerId in zip(game.players, playerOrder))
		positions = []

		for position in game.board.positions:
			if not position.isOccupied:
				continue

			try:
				occupantPlayerId = playerDataByObject[position.occupant]["playerId"]
			except KeyError as error:
				raise ValueError("Board contains a player without persistent metadata") from error

			positions.append(PositionState.fromPosition(position, occupantPlayerId))

		activePlayerId = None

		if game.activePlayer is not None:
			try:
				activePlayerId = playerDataByObject[game.activePlayer]["playerId"]
			except KeyError as error:
				raise ValueError("Active player has no persistent metadata") from error

		return cls(
			isStarted=game.isStarted,
			isFinished=game.isFinished,
			handsFinished=game.handsFinished,
			activePlayerIndex=game.activePlayerIndex,
			activePlayerId=activePlayerId,
			dealerRotationCount=game.dealerRotationCount,
			boardColors=game.board.colors,
			playerOrder=playerOrder,
			players=players,
			positions=tuple(positions),
			deck=DeckState.fromDeck(game.deck),
		)

	def restoreGame(self, session) -> Game:
		playerDataById = {}

		for playerData in session.players.values():
			playerId = playerData.get("playerId")

			if playerId in playerDataById:
				raise ValueError("Session contains duplicate persistent player IDs")

			playerDataById[playerId] = playerData

		if set(playerDataById) != set(self.playerOrder):
			raise ValueError("Session players do not match game snapshot")

		try:
			players = [playerDataById[playerId]["object"] for playerId in self.playerOrder]
		except KeyError as error:
			raise ValueError("Session player has no runtime object") from error

		game = Game(session, list(self.boardColors), session.rules)

		for player in players:
			player.setDealer(False)
			player.resetPiecesOnTheBoard()

		game.setPlayers(players)

		drawPile = [cardState.toCard() for cardState in self.deck.drawPile]
		discardPile = [cardState.toCard() for cardState in self.deck.discardPile]
		deck = Deck.fromPiles(drawPile, discardPile)

		for playerState in self.players:
			player = playerDataById[playerState.playerId]["object"]
			player.restoreHand([cardState.toCard(deck) for cardState in playerState.hand])

		for positionState in self.positions:
			try:
				if positionState.positionId.startswith("house-"):
					position = game.board.getHouseById(positionState.positionId)
				else:
					position = game.board.getSpotById(positionState.positionId)
			except IndexError as error:
				raise ValueError(f"Snapshot position does not exist on this board: {positionState.positionId}") from error

			player = playerDataById[positionState.playerId]["object"]
			position.setOccupant(player, positionState.isFreshlyDeployed, positionState.isBlocking)
			player.addAPieceOnTheBoard()

		activePlayer = None

		if self.activePlayerId is not None:
			activePlayer = playerDataById[self.activePlayerId]["object"]

		game.restoreRuntimeState(
			deck,
			self.isStarted,
			self.isFinished,
			self.handsFinished,
			self.activePlayerIndex,
			activePlayer,
			self.dealerRotationCount,
		)

		session.game = game
		return game

@dataclass(frozen=True, slots=True)
class SessionSnapshotState:
	metadata: SessionMetadataState
	game: GameState
	events: tuple[GameEvent, ...]
	progress: GameProgressState

	def __post_init__(self) -> None:
		if not isinstance(self.metadata, SessionMetadataState):
			raise ValueError("Invalid snapshot metadata")

		if not isinstance(self.game, GameState):
			raise ValueError("Invalid snapshot game state")

		if not isinstance(self.progress, GameProgressState):
			raise ValueError("Invalid snapshot game progress")

		if type(self.events) is not tuple or not all(isinstance(event, GameEvent) for event in self.events):
			raise ValueError("Invalid snapshot event log")

		metadataPlayerIds = {player.playerId for player in self.metadata.players}

		if metadataPlayerIds != set(self.game.playerOrder):
			raise ValueError("Snapshot metadata and game players do not match")

		if not self.progress.referencedPlayerIds.issubset(metadataPlayerIds):
			raise ValueError("Game progress references an unknown player")

		if self.progress.dealIndex >= len(self.metadata.rules.deal_card_counts):
			raise ValueError("Game progress references an invalid deal")

		previousElapsedSeconds = -1

		for expectedSequence, event in enumerate(self.events, start=1):
			if event.sequence != expectedSequence:
				raise ValueError("Snapshot event sequence is not contiguous")

			if event.elapsedSeconds < previousElapsedSeconds:
				raise ValueError("Snapshot event times are not ordered")

			if event.playerId is not None and event.playerId not in metadataPlayerIds:
				raise ValueError("Snapshot event references an unknown player")

			previousElapsedSeconds = event.elapsedSeconds

	def to_dict(self) -> dict:
		return {
			"metadata": self.metadata.to_dict(),
			"game": self.game.to_dict(),
			"events": [event.to_dict() for event in self.events],
			"progress": self.progress.to_dict(),
		}

	@classmethod
	def from_dict(cls, values: dict) -> "SessionSnapshotState":
		if type(values["events"]) is not list:
			raise ValueError("Invalid snapshot event log")

		if type(values) is not dict or set(values) != {"metadata", "game", "progress", "events"}:
			raise ValueError("Invalid session snapshot")

		return cls(
			metadata=SessionMetadataState.from_dict(values["metadata"]),
			game=GameState.from_dict(values["game"]),
			events=tuple(GameEvent.from_dict(event) for event in values["events"]),
			progress=GameProgressState.from_dict(values["progress"]),
		)

	@classmethod
	def fromGameSession(cls, session) -> "SessionSnapshotState":
		return cls(
			metadata=session.metadataState(),
			game=GameState.fromGameSession(session),
			events=session.events,
			progress=session.gameProgress,
		)