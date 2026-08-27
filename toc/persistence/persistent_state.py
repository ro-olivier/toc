from dataclasses import dataclass
from uuid import UUID
from datetime import datetime, timezone

from toc.model.rules import GameRules
from toc.infrastructure.versions import ARCHIVE_FORMAT_VERSION, ENGINE_VERSION, RULES_FORMAT_VERSION
from toc.model.game_mode import GameModeDefinition

def _validatePersistentId(value: str, fieldName: str) -> None:
	if type(value) is not str:
		raise ValueError(f"Invalid {fieldName}")

	try:
		normalisedId = UUID(hex=value).hex
	except (TypeError, ValueError, AttributeError) as error:
		raise ValueError(f"Invalid {fieldName}") from error

	if normalisedId != value:
		raise ValueError(f"Invalid {fieldName}")

@dataclass(frozen=True, slots=True)
class ParticipantMetadataState:
	participantId: str
	name: str
	configured: bool
	resumeTokenHash: str

	def __post_init__(self) -> None:
		_validatePersistentId(self.participantId, "participant ID")

		if type(self.name) is not str or not self.name:
			raise ValueError("Invalid participant name")

		if type(self.configured) is not bool:
			raise ValueError("Invalid participant configuration state")

		if type(self.resumeTokenHash) is not str or len(self.resumeTokenHash) != 64:
			raise ValueError("Invalid participant resume token hash")

		try:
			int(self.resumeTokenHash, 16)
		except ValueError as error:
			raise ValueError("Invalid participant resume token hash") from error

	def to_dict(self) -> dict:
		return {
			"participantId": self.participantId,
			"name": self.name,
			"configured": self.configured,
			"resumeTokenHash": self.resumeTokenHash,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "ParticipantMetadataState":
		expectedFields = {"participantId", "name", "configured", "resumeTokenHash"}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid participant metadata")

		return cls(
			participantId=values["participantId"],
			name=values["name"],
			configured=values["configured"],
			resumeTokenHash=values["resumeTokenHash"],
		)

	@classmethod
	def fromParticipant(cls, participant) -> "ParticipantMetadataState":
		return cls(
			participantId=participant.participantId,
			name=participant.name,
			configured=participant.configured,
			resumeTokenHash=participant.resumeTokenHash,
		)

@dataclass(frozen=True, slots=True)
class SeatMetadataState:
	seatId: str
	participantId: str
	team: str
	color: str

	def __post_init__(self) -> None:
		_validatePersistentId(self.seatId, "seat ID")
		_validatePersistentId(self.participantId, "seat participant ID")

		if type(self.team) is not str or not self.team:
			raise ValueError("Invalid seat team")

		if type(self.color) is not str or not self.color:
			raise ValueError("Invalid seat colour")

	def to_dict(self) -> dict:
		return {
			"seatId": self.seatId,
			"participantId": self.participantId,
			"team": self.team,
			"color": self.color,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "SeatMetadataState":
		expectedFields = {"seatId", "participantId", "team", "color"}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid seat metadata")

		return cls(
			seatId=values["seatId"],
			participantId=values["participantId"],
			team=values["team"],
			color=values["color"],
		)

	@classmethod
	def fromSeat(cls, seat) -> "SeatMetadataState":
		return cls(
			seatId=seat.seatId,
			participantId=seat.participantId,
			team=seat.team,
			color=seat.color,
		)


@dataclass(frozen=True, slots=True)
class SessionMetadataState:
	archiveFormatVersion: int
	engineVersion: str
	rulesFormatVersion: int
	sessionId: str
	joinCode: str
	modeDefinition: GameModeDefinition
	rulesetName: str
	rules: GameRules
	participants: tuple[ParticipantMetadataState, ...]
	seats: tuple[SeatMetadataState, ...]
	createdAt: datetime
	startedAt: datetime | None
	endedAt: datetime | None
	lastActivityAt: datetime

	def __post_init__(self) -> None:
		if type(self.participants) is not tuple or not all(isinstance(participant, ParticipantMetadataState) for participant in self.participants):
			raise ValueError("Invalid participant metadata collection")

		if type(self.seats) is not tuple or not all(isinstance(seat, SeatMetadataState) for seat in self.seats):
			raise ValueError("Invalid seat metadata collection")

		participantIds = [participant.participantId for participant in self.participants]
		seatIds = [seat.seatId for seat in self.seats]

		if len(participantIds) != len(set(participantIds)):
			raise ValueError("Participant metadata contains duplicate IDs")

		if len(seatIds) != len(set(seatIds)):
			raise ValueError("Seat metadata contains duplicate IDs")

		if any(seat.participantId not in participantIds for seat in self.seats):
			raise ValueError("Seat metadata references an unknown participant")

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
			"startedAt": self.startedAt.isoformat() if self.startedAt is not None else None,
			"endedAt": self.endedAt.isoformat() if self.endedAt is not None else None,
			"lastActivityAt": self.lastActivityAt.isoformat(),
		}

	@classmethod
	def from_dict(cls, values: dict) -> "SessionMetadataState":
		if type(values) is not dict:
			raise ValueError("Session metadata must be an object")

		if values.get("archiveFormatVersion") != ARCHIVE_FORMAT_VERSION:
			raise ValueError("Unsupported archive format version")

		if values.get("rulesFormatVersion") != RULES_FORMAT_VERSION:
			raise ValueError("Unsupported rules format version")

		if type(values.get("engineVersion")) is not str or not values["engineVersion"]:
			raise ValueError("Invalid engine version")

		sessionId = values.get("sessionId")

		if type(sessionId) is not str or UUID(hex=sessionId).hex != sessionId:
			raise ValueError("Invalid session ID")

		if type(values.get("joinCode")) is not str or not values["joinCode"]:
			raise ValueError("Invalid join code")

		ruleset = values.get("ruleset")

		if type(ruleset) is not dict or set(ruleset) != {"preset", "values"}:
			raise ValueError("Invalid ruleset metadata")

		if type(ruleset["preset"]) is not str or not ruleset["preset"]:
			raise ValueError("Invalid ruleset name")

		modeDefinition = GameModeDefinition.from_dict(values.get("gameMode"))

		participants = values.get("participants")
		seats = values.get("seats")

		if type(participants) is not list:
			raise ValueError("Invalid participant metadata list")

		if type(seats) is not list:
			raise ValueError("Invalid seat metadata list")

		return cls(
			archiveFormatVersion=values["archiveFormatVersion"],
			engineVersion=values["engineVersion"],
			rulesFormatVersion=values["rulesFormatVersion"],
			sessionId=sessionId,
			joinCode=values["joinCode"],
			modeDefinition=modeDefinition,
			rulesetName=ruleset["preset"],
			rules=GameRules.from_dict(ruleset["values"]),
			participants=tuple(ParticipantMetadataState.from_dict(participant) for participant in participants),
			seats=tuple(SeatMetadataState.from_dict(seat) for seat in seats),
			createdAt=_parseTimestamp(values.get("createdAt"), "creation timestamp"),
			startedAt=_parseTimestamp(values.get("startedAt"), "start timestamp", optional=True),
			endedAt=_parseTimestamp(values.get("endedAt"), "end timestamp", optional=True),
			lastActivityAt=_parseTimestamp(values.get("lastActivityAt"), "last activity timestamp"),
		)

	@classmethod
	def fromGameSession(cls, session) -> "SessionMetadataState":
		return cls(
			archiveFormatVersion=ARCHIVE_FORMAT_VERSION,
			engineVersion=ENGINE_VERSION,
			rulesFormatVersion=RULES_FORMAT_VERSION,
			sessionId=session.sessionId,
			joinCode=session.joinCode,
			modeDefinition=session.modeDefinition,
			rulesetName=session.rulesetName,
			rules=session.rules,
			participants=tuple(ParticipantMetadataState.fromParticipant(participant) for participant in session.roster.participants),
			seats=tuple(SeatMetadataState.fromSeat(seat) for seat in session.roster.seats),
			createdAt=session.createdAt,
			startedAt=session.startedAt,
			endedAt=session.endedAt,
			lastActivityAt=session.lastActivityAt,
		)

def _parseTimestamp(value, fieldName: str, optional: bool = False):
	if value is None and optional:
		return None

	if type(value) is not str:
		raise ValueError(f"Invalid {fieldName}")

	try:
		timestamp = datetime.fromisoformat(value)
	except ValueError as error:
		raise ValueError(f"Invalid {fieldName}") from error

	if timestamp.tzinfo is None or timestamp.utcoffset() is None:
		raise ValueError(f"{fieldName} must include a timezone")

	return timestamp.astimezone(timezone.utc)
	