import json

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable


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


def _validateJsonValue(value) -> None:
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


def _normaliseDetails(details: dict) -> dict:
	if type(details) is not dict:
		raise ValueError("Audit-event details must be an object")

	_validateJsonValue(details)

	try:
		encoded = json.dumps(details, allow_nan=False)
	except (TypeError, ValueError) as error:
		raise ValueError("Audit-event details are not JSON-compatible") from error

	return json.loads(encoded)


@dataclass(frozen=True, slots=True)
class GameEvent:
	sequence: int
	elapsedSeconds: int
	eventType: GameEventType
	playerId: str | None
	details: dict

	def __post_init__(self) -> None:
		if type(self.sequence) is not int or self.sequence < 1:
			raise ValueError("Audit-event sequence must be a positive integer")

		if type(self.elapsedSeconds) is not int or self.elapsedSeconds < 0:
			raise ValueError("Audit-event elapsed time must be a non-negative integer")

		if not isinstance(self.eventType, GameEventType):
			raise ValueError("Invalid audit-event type")

		if self.playerId is not None and (type(self.playerId) is not str or not self.playerId):
			raise ValueError("Invalid audit-event player ID")

		object.__setattr__(self, "details", _normaliseDetails(self.details))

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
	def __init__(self, elapsedSecondsProvider: Callable[[], int]):
		self._elapsedSecondsProvider = elapsedSecondsProvider
		self._events = []

	@property
	def events(self) -> tuple[GameEvent, ...]:
		return tuple(self._events)

	def record(self, eventType: GameEventType, playerId: str = None, details: dict = None) -> GameEvent:
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

	def to_list(self) -> list[dict]:
		return [event.to_dict() for event in self._events]

	@classmethod
	def from_list(cls, values: list, elapsedSecondsProvider: Callable[[], int]) -> "GameEventLog":
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