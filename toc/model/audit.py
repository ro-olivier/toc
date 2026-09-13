import json

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from toc.model.params import JOKER_COLORS, JOKER_VALUE, SUITS, VALUES


class GameEventType(StrEnum):
	GAME_STARTED = "game-started"
	CARDS_DEALT = "cards-dealt"
	CARD_EXCHANGED = "card-exchanged"
	TURN_STARTED = "turn-started"
	CARD_PLAYED = "card-played"
	CARD_DISCARDED = "card-discarded"
	HAND_FOLDED = "hand-folded"
	PIECE_MOVED = "piece-moved"
	PIECE_KICKED = "piece-kicked"
	SEVEN_HOP_DECIDED = "seven-hop-decided"
	DEALER_CHANGED = "dealer-changed"
	GAME_FINISHED = "game-finished"

EVENT_DETAIL_FIELDS = {
	GameEventType.GAME_STARTED: set(),
	GameEventType.CARDS_DEALT: {"deckCycle", "deal", "cards"},
	GameEventType.CARD_EXCHANGED: {"partnerId", "givenCard", "receivedCard"},
	GameEventType.TURN_STARTED: {"handSize"},
	GameEventType.CARD_PLAYED: {"card", "moveType", "pieceOwnerId", "originPositionId", "targetPositionId", "steps"},
	GameEventType.CARD_DISCARDED: {"reason", "card"},
	GameEventType.HAND_FOLDED: {"reason", "cards"},
	GameEventType.PIECE_MOVED: {"moveType", "pieceOwnerId", "originPositionId", "targetPositionId", "steps"},
	GameEventType.PIECE_KICKED: {"pieceOwnerId", "positionId", "reason"},
	GameEventType.SEVEN_HOP_DECIDED: {"actingPlayerId", "pieceOwnerId", "originPositionId", "targetPositionId", "accepted"},
	GameEventType.DEALER_CHANGED: {"rotationCount", "initial"},
	GameEventType.GAME_FINISHED: {"winningTeam", "winningSeatIds", "winningParticipantIds", "winnerNames"},
}

MOVE_TYPES = {"OUT", "MOVE", "BACK", "FIVE", "HOP", "SWITCH", "ENTER", "SEVEN"}

def _validateString(value: object, fieldName: str, allowNone: bool = False) -> None:
	if value is None and allowNone:
		return

	if type(value) is not str or not value:
		raise ValueError(f"Invalid audit-event {fieldName}")


def _validateInteger(value: object, fieldName: str, minimum: int = 0) -> None:
	if type(value) is not int or value < minimum:
		raise ValueError(f"Invalid audit-event {fieldName}")


def _validateCardData(value: object, fieldName: str) -> None:
	if type(value) is not dict or set(value) != {"suit", "value"}:
		raise ValueError(f"Invalid audit-event {fieldName}")

	_validateString(value["suit"], f"{fieldName} suit")
	_validateString(value["value"], f"{fieldName} value")

	standardCard = value["suit"] in SUITS and value["value"] in VALUES
	jokerCard = value["suit"] in JOKER_COLORS and value["value"] == JOKER_VALUE

	if not standardCard and not jokerCard:
		raise ValueError(f"Invalid audit-event {fieldName}")


def _validateCardList(value: object, fieldName: str) -> None:
	if type(value) is not list or not value:
		raise ValueError(f"Invalid audit-event {fieldName}")

	for card in value:
		_validateCardData(card, fieldName)


def _validateStringList(value: object, fieldName: str) -> None:
	if type(value) is not list or any(type(item) is not str or not item for item in value):
		raise ValueError(f"Invalid audit-event {fieldName}")


def _validateMovementData(details: dict[str, object], requireTarget: bool) -> None:
	if details["moveType"] not in MOVE_TYPES:
		raise ValueError("Invalid audit-event move type")

	_validateString(details["pieceOwnerId"], "piece owner ID")
	_validateString(details["originPositionId"], "origin position ID", allowNone=True)
	_validateString(details["targetPositionId"], "target position ID", allowNone=not requireTarget)

	if details["steps"] is not None:
		_validateInteger(details["steps"], "step count", 1)


def _validateJsonValue(value: object) -> None:
	if value is None or type(value) in (str, int, float, bool):
		return

	if type(value) in (list, tuple):
		for item in value:
			_validateJsonValue(item)

		return

	if type(value) is dict:
		if any(type(key) is not str for key in value):
			raise ValueError("Audit-event object keys must be strings")

		for item in value.values():
			_validateJsonValue(item)

		return

	raise ValueError(f"Audit-event value is not JSON-compatible: {type(value).__name__}")


def _normaliseDetails(details: dict[str, object]) -> dict[str, object]:
	if type(details) is not dict:
		raise ValueError("Audit-event details must be an object")

	_validateJsonValue(details)

	try:
		encoded = json.dumps(details, allow_nan=False)
	except (TypeError, ValueError) as error:
		raise ValueError("Audit-event details are not JSON-compatible") from error

	return json.loads(encoded)

def _validateEventDetails(eventType: GameEventType, details: dict[str, object]) -> None:
	if set(details) != EVENT_DETAIL_FIELDS[eventType]:
		raise ValueError(f"Invalid details for audit event '{eventType.value}'")

	if eventType is GameEventType.GAME_STARTED:
		return

	if eventType is GameEventType.CARDS_DEALT:
		_validateInteger(details["deckCycle"], "deck cycle", 1)
		_validateInteger(details["deal"], "deal number", 1)
		_validateCardList(details["cards"], "dealt cards")

	elif eventType is GameEventType.CARD_EXCHANGED:
		_validateString(details["partnerId"], "exchange partner ID")
		_validateCardData(details["givenCard"], "given card")
		_validateCardData(details["receivedCard"], "received card")

	elif eventType is GameEventType.TURN_STARTED:
		_validateInteger(details["handSize"], "hand size")

	elif eventType is GameEventType.CARD_PLAYED:
		_validateCardData(details["card"], "played card")
		_validateMovementData(details, requireTarget=False)

		if details["moveType"] == "SEVEN":
			if details["originPositionId"] is not None or details["targetPositionId"] is not None:
				raise ValueError("Invalid audit-event seven positions")
		elif details["originPositionId"] is None or details["targetPositionId"] is None:
			raise ValueError("Invalid audit-event played-card positions")

	elif eventType is GameEventType.CARD_DISCARDED:
		if details["reason"] != "no-legal-move":
			raise ValueError("Invalid audit-event discard reason")

		_validateCardData(details["card"], "discarded card")

	elif eventType is GameEventType.HAND_FOLDED:
		if details["reason"] != "no-legal-move":
			raise ValueError("Invalid audit-event fold reason")

		_validateCardList(details["cards"], "folded cards")

	elif eventType is GameEventType.PIECE_MOVED:
		_validateMovementData(details, requireTarget=True)

		if details["moveType"] == "OUT" and details["originPositionId"] is not None:
			raise ValueError("Invalid audit-event deployment origin")

		if details["moveType"] != "OUT" and details["originPositionId"] is None:
			raise ValueError("Invalid audit-event movement origin")

	elif eventType is GameEventType.PIECE_KICKED:
		_validateString(details["pieceOwnerId"], "kicked piece owner ID")
		_validateString(details["positionId"], "kick position ID")

		if details["reason"] not in {"path", "landing"}:
			raise ValueError("Invalid audit-event kick reason")

	elif eventType is GameEventType.SEVEN_HOP_DECIDED:
		_validateString(details["actingPlayerId"], "acting player ID")
		_validateString(details["pieceOwnerId"], "piece owner ID")
		_validateString(details["originPositionId"], "hop origin position ID")
		_validateString(details["targetPositionId"], "hop target position ID")

		if type(details["accepted"]) is not bool:
			raise ValueError("Invalid audit-event seven-hop decision")

	elif eventType is GameEventType.DEALER_CHANGED:
		_validateInteger(details["rotationCount"], "dealer rotation count")

		if type(details["initial"]) is not bool:
			raise ValueError("Invalid audit-event initial-dealer flag")

		if details["initial"] and details["rotationCount"] != 0:
			raise ValueError("Initial dealer must have rotation count zero")

	elif eventType is GameEventType.GAME_FINISHED:
		_validateString(details["winningTeam"], "winning team", allowNone=True)
		_validateStringList(details["winningSeatIds"], "winning seat IDs")
		_validateStringList(details["winningParticipantIds"], "winning participant IDs")
		_validateStringList(details["winnerNames"], "winner names")

		if len(details["winningParticipantIds"]) != len(details["winnerNames"]):
			raise ValueError("Winning participants and names do not match")

		if details["winningTeam"] is None and any((details["winningSeatIds"], details["winningParticipantIds"], details["winnerNames"])):
			raise ValueError("Finished event without a winning team cannot contain winners")

		if details["winningTeam"] is not None and not all((details["winningSeatIds"], details["winningParticipantIds"], details["winnerNames"])):
			raise ValueError("Finished event with a winning team must contain winners")


@dataclass(frozen=True, slots=True)
class GameEvent:
	sequence: int
	elapsedSeconds: int
	eventType: GameEventType
	playerId: str | None
	details: dict[str, object]

	def __post_init__(self) -> None:
		if type(self.sequence) is not int or self.sequence < 1:
			raise ValueError("Audit-event sequence must be a positive integer")

		if type(self.elapsedSeconds) is not int or self.elapsedSeconds < 0:
			raise ValueError("Audit-event elapsed time must be a non-negative integer")

		if not isinstance(self.eventType, GameEventType):
			raise ValueError("Invalid audit-event type")

		if self.playerId is not None and (type(self.playerId) is not str or not self.playerId):
			raise ValueError("Invalid audit-event player ID")

		if self.eventType in {GameEventType.GAME_STARTED, GameEventType.GAME_FINISHED} and self.playerId is not None:
			raise ValueError("System audit event cannot reference a player")

		if self.eventType not in {GameEventType.GAME_STARTED, GameEventType.GAME_FINISHED} and self.playerId is None:
			raise ValueError("Player audit event must reference a player")

		normalisedDetails = _normaliseDetails(self.details)
		_validateEventDetails(self.eventType, normalisedDetails)
		object.__setattr__(self, "details", normalisedDetails)

	def to_dict(self) -> dict:
		return {
			"sequence": self.sequence,
			"elapsedSeconds": self.elapsedSeconds,
			"type": self.eventType.value,
			"playerId": self.playerId,
			"details": self.details,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "GameEvent":
		expectedFields = {"sequence", "elapsedSeconds", "type", "playerId", "details"}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid audit-event data")

		try:
			eventType = GameEventType(values["type"])
		except (TypeError, ValueError) as error:
			raise ValueError("Invalid audit-event type") from error

		return cls(
			sequence=values["sequence"],
			elapsedSeconds=values["elapsedSeconds"],
			eventType=eventType,
			playerId=values["playerId"],
			details=values["details"],
		)


class GameEventLog:
	def __init__(self, elapsedSecondsProvider: Callable[[], int]) -> None:
		self._elapsedSecondsProvider = elapsedSecondsProvider
		self._events: list[GameEvent] = []

	@property
	def events(self) -> tuple[GameEvent, ...]:
		return tuple(self._events)

	def record(self, eventType: GameEventType, playerId: str | None = None, details: dict[str, object] | None = None) -> GameEvent:
		elapsedSeconds = max(0, int(self._elapsedSecondsProvider()))

		event = GameEvent(
			sequence=len(self._events) + 1,
			elapsedSeconds=elapsedSeconds,
			eventType=eventType,
			playerId=playerId,
			details={} if details is None else details,
		)

		self._events.append(event)
		return event

	def to_list(self) -> list[dict[str, object]]:
		return [event.to_dict() for event in self._events]

	@classmethod
	def from_list(cls, values: list[dict[str, object]], elapsedSecondsProvider: Callable[[], int]) -> "GameEventLog":
		if type(values) is not list:
			raise ValueError("Audit-event log must be an array")

		eventLog = cls(elapsedSecondsProvider)
		previousElapsedSeconds = -1

		for expectedSequence, eventData in enumerate(values, start=1):
			event = GameEvent.from_dict(eventData)

			if event.sequence != expectedSequence:
				raise ValueError("Audit-event sequence is not contiguous")

			if event.elapsedSeconds < previousElapsedSeconds:
				raise ValueError("Audit-event elapsed times are not ordered")

			eventLog._events.append(event)
			previousElapsedSeconds = event.elapsedSeconds

		return eventLog