from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from toc.infrastructure.versions import ARCHIVE_FORMAT_VERSION, ENGINE_VERSION, RULES_FORMAT_VERSION
from toc.model.audit import GameEvent, GameEventType
from toc.model.rules import GameRules
from toc.persistence.snapshot_state import GameState
from toc.model.game_mode import GameModeDefinition


def _validateId(value: str, fieldName: str) -> None:
	if type(value) is not str:
		raise ValueError(f"Invalid {fieldName}")

	try:
		normalisedId = UUID(hex=value).hex
	except (ValueError, AttributeError) as error:
		raise ValueError(f"Invalid {fieldName}") from error

	if normalisedId != value:
		raise ValueError(f"Invalid {fieldName}")


def _parseTimestamp(value, fieldName: str) -> datetime:
	if type(value) is not str:
		raise ValueError(f"Invalid {fieldName}")

	try:
		timestamp = datetime.fromisoformat(value)
	except ValueError as error:
		raise ValueError(f"Invalid {fieldName}") from error

	if timestamp.tzinfo is None or timestamp.utcoffset() is None:
		raise ValueError(f"{fieldName} must include a timezone")

	return timestamp.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class FinishedParticipantState:
	participantId: str
	name: str

	def __post_init__(self) -> None:
		_validateId(self.participantId, "finished-participant ID")

		if type(self.name) is not str or not self.name:
			raise ValueError("Invalid finished-participant name")

	def to_dict(self) -> dict:
		return {
			"participantId": self.participantId,
			"name": self.name,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "FinishedParticipantState":
		if type(values) is not dict or set(values) != {"participantId", "name"}:
			raise ValueError("Invalid finished-participant data")

		return cls(participantId=values["participantId"], name=values["name"])

	@classmethod
	def fromParticipant(cls, participant) -> "FinishedParticipantState":
		return cls(participantId=participant.participantId, name=participant.name)

@dataclass(frozen=True, slots=True)
class FinishedSeatState:
	seatId: str
	participantId: str
	team: str
	color: str

	def __post_init__(self) -> None:
		_validateId(self.seatId, "finished-seat ID")
		_validateId(self.participantId, "finished-seat participant ID")

		if type(self.team) is not str or not self.team:
			raise ValueError("Invalid finished-seat team")

		if type(self.color) is not str or not self.color:
			raise ValueError("Invalid finished-seat colour")

	def to_dict(self) -> dict:
		return {
			"seatId": self.seatId,
			"participantId": self.participantId,
			"team": self.team,
			"color": self.color,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "FinishedSeatState":
		if type(values) is not dict or set(values) != {"seatId", "participantId", "team", "color"}:
			raise ValueError("Invalid finished-seat data")

		return cls(
			seatId=values["seatId"],
			participantId=values["participantId"],
			team=values["team"],
			color=values["color"],
		)

	@classmethod
	def fromSeat(cls, seat) -> "FinishedSeatState":
		return cls(seatId=seat.seatId, participantId=seat.participantId, team=seat.team, color=seat.color)


@dataclass(frozen=True, slots=True)
class FinishedArchiveState:
	archiveFormatVersion: int
	engineVersion: str
	rulesFormatVersion: int
	sessionId: str
	joinCode: str
	modeDefinition: GameModeDefinition
	rulesetName: str
	rules: GameRules
	participants: tuple[FinishedParticipantState, ...]
	seats: tuple[FinishedSeatState, ...]
	createdAt: datetime
	startedAt: datetime
	endedAt: datetime
	game: GameState
	events: tuple[GameEvent, ...]

	def __post_init__(self) -> None:
		if self.archiveFormatVersion != ARCHIVE_FORMAT_VERSION:
			raise ValueError("Unsupported archive format version")

		if type(self.engineVersion) is not str or not self.engineVersion:
			raise ValueError("Invalid engine version")

		if self.rulesFormatVersion != RULES_FORMAT_VERSION:
			raise ValueError("Unsupported rules format version")

		_validateId(self.sessionId, "finished session ID")

		if type(self.joinCode) is not str or not self.joinCode:
			raise ValueError("Invalid finished-game join code")

		if type(self.rulesetName) is not str or not self.rulesetName:
			raise ValueError("Invalid finished-game ruleset name")

		if not isinstance(self.rules, GameRules):
			raise ValueError("Invalid finished-game rules")

		if not isinstance(self.modeDefinition, GameModeDefinition):
			raise ValueError("Invalid finished-game mode")

		if not isinstance(self.game, GameState):
			raise ValueError("Invalid finished-game state")

		if type(self.events) is not tuple or not self.events:
			raise ValueError("Invalid finished-game event log")

		if self.startedAt < self.createdAt:
			raise ValueError("Game start timestamp cannot precede creation")

		if self.endedAt < self.startedAt:
			raise ValueError("Game end timestamp cannot precede start")

		if not self.game.isStarted or not self.game.isFinished:
			raise ValueError("Finished archive must contain a finished game")

		if type(self.participants) is not tuple or not self.participants or not all(isinstance(participant, FinishedParticipantState) for participant in self.participants):
			raise ValueError("Invalid finished-game participants")

		if type(self.seats) is not tuple or not self.seats or not all(isinstance(seat, FinishedSeatState) for seat in self.seats):
			raise ValueError("Invalid finished-game seats")

		if len(self.participants) != self.modeDefinition.participantCount:
			raise ValueError("Finished archive participant count does not match game mode")

		if len(self.seats) != self.modeDefinition.seatCount:
			raise ValueError("Finished archive seat count does not match game mode")

		previousElapsedSeconds = -1

		for expectedSequence, event in enumerate(self.events, start=1):
			if event.sequence != expectedSequence:
				raise ValueError("Finished-game event sequence is not contiguous")

			if event.elapsedSeconds < previousElapsedSeconds:
				raise ValueError("Finished-game event elapsed times are not ordered")

			if event.playerId is not None and event.playerId not in seatIds:
				raise ValueError("Finished-game event references an unknown player")

			previousElapsedSeconds = event.elapsedSeconds

		if self.events[-1].eventType is not GameEventType.GAME_FINISHED:
			raise ValueError("Finished archive must end with a game-finished event")

		participantIds = [participant.participantId for participant in self.participants]
		seatIds = [seat.seatId for seat in self.seats]

		if len(participantIds) != len(set(participantIds)):
			raise ValueError("Finished archive contains duplicate participant IDs")

		if len({participant.name for participant in self.participants}) != len(self.participants):
			raise ValueError("Finished archive contains duplicate participant names")

		if len(seatIds) != len(set(seatIds)):
			raise ValueError("Finished archive contains duplicate seat IDs")

		if any(seat.participantId not in participantIds for seat in self.seats):
			raise ValueError("Finished archive seat references an unknown participant")

		if set(seatIds) != set(self.game.playerOrder):
			raise ValueError("Finished archive seats do not match game seats")

	def to_dict(self) -> dict:
		return {
			"archiveFormatVersion": self.archiveFormatVersion,
			"engineVersion": self.engineVersion,
			"rulesFormatVersion": self.rulesFormatVersion,
			"sessionId": self.sessionId,
			"joinCode": self.joinCode,
			"ruleset": {
				"preset": self.rulesetName,
				"values": self.rules.to_dict(),
			},
			"gameMode": self.modeDefinition.to_dict(),
			"participants": [participant.to_dict() for participant in self.participants],
			"seats": [seat.to_dict() for seat in self.seats],
			"createdAt": self.createdAt.isoformat(),
			"startedAt": self.startedAt.isoformat(),
			"endedAt": self.endedAt.isoformat(),
			"game": self.game.to_dict(),
			"events": [event.to_dict() for event in self.events],
		}

	@classmethod
	def from_dict(cls, values: dict) -> "FinishedArchiveState":
		expectedFields = {
			"archiveFormatVersion",
			"engineVersion",
			"rulesFormatVersion",
			"sessionId",
			"joinCode",
			"ruleset",
			"gameMode",
			"participants",
			"seats",
			"createdAt",
			"startedAt",
			"endedAt",
			"game",
			"events",
		}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid finished archive")

		ruleset = values["ruleset"]

		if type(ruleset) is not dict or set(ruleset) != {"preset", "values"}:
			raise ValueError("Invalid finished-game ruleset")

		if type(values["participants"]) is not list:
			raise ValueError("Invalid finished-game participants")

		if type(values["seats"]) is not list:
			raise ValueError("Invalid finished-game seats")

		if type(values["events"]) is not list:
			raise ValueError("Invalid finished-game events")

		return cls(
			archiveFormatVersion=values["archiveFormatVersion"],
			engineVersion=values["engineVersion"],
			rulesFormatVersion=values["rulesFormatVersion"],
			sessionId=values["sessionId"],
			joinCode=values["joinCode"],
			rulesetName=ruleset["preset"],
			rules=GameRules.from_dict(ruleset["values"]),
			modeDefinition = GameModeDefinition.from_dict(values["gameMode"]),
			participants=tuple(FinishedParticipantState.from_dict(participant) for participant in values["participants"]),
			seats=tuple(FinishedSeatState.from_dict(seat) for seat in values["seats"]),
			createdAt=_parseTimestamp(values["createdAt"], "creation timestamp"),
			startedAt=_parseTimestamp(values["startedAt"], "start timestamp"),
			endedAt=_parseTimestamp(values["endedAt"], "end timestamp"),
			game=GameState.from_dict(values["game"]),
			events=tuple(GameEvent.from_dict(event) for event in values["events"]),
		)

	@classmethod
	def fromGameSession(cls, session) -> "FinishedArchiveState":
		if session.game is None or not session.game.isFinished:
			raise ValueError("Cannot archive an unfinished game")

		if session.startedAt is None or session.endedAt is None:
			raise ValueError("Finished game timestamps are incomplete")

		return cls(
			archiveFormatVersion=ARCHIVE_FORMAT_VERSION,
			engineVersion=ENGINE_VERSION,
			rulesFormatVersion=RULES_FORMAT_VERSION,
			sessionId=session.sessionId,
			joinCode=session.joinCode,
			rulesetName=session.rulesetName,
			rules=session.rules,
			modeDefinition=session.modeDefinition,
			participants=tuple(FinishedParticipantState.fromParticipant(participant) for participant in session.roster.participants),
			seats=tuple(FinishedSeatState.fromSeat(seat) for seat in session.roster.seats),
			createdAt=session.createdAt,
			startedAt=session.startedAt,
			endedAt=session.endedAt,
			game=GameState.fromGameSession(session),
			events=session.events,
		)