from dataclasses import dataclass
from uuid import UUID
from datetime import datetime, timezone

from rules import GameRules
from versions import ARCHIVE_FORMAT_VERSION, ENGINE_VERSION, RULES_FORMAT_VERSION


@dataclass(frozen=True, slots=True)
class PlayerMetadataState:
	playerId: str
	name: str
	team: str
	color: str
	configured: bool
	resumeTokenHash: str

	def to_dict(self) -> dict:
		return {
			"playerId": self.playerId,
			"name": self.name,
			"team": self.team,
			"color": self.color,
			"configured": self.configured,
			"resumeTokenHash": self.resumeTokenHash,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "PlayerMetadataState":
		expectedFields = {"playerId", "name", "team", "color", "configured", "resumeTokenHash"}

		if type(values) is not dict or set(values) != expectedFields:
			raise ValueError("Invalid player metadata")

		if type(values["playerId"]) is not str or UUID(hex=values["playerId"]).hex != values["playerId"]:
			raise ValueError("Invalid persistent player ID")

		if type(values["name"]) is not str or not values["name"]:
			raise ValueError("Invalid player name")

		if type(values["team"]) is not str:
			raise ValueError("Invalid player team")

		if type(values["color"]) is not str:
			raise ValueError("Invalid player color")

		if type(values["configured"]) is not bool:
			raise ValueError("Invalid player configuration state")

		resumeTokenHash = values["resumeTokenHash"]

		if type(resumeTokenHash) is not str or len(resumeTokenHash) != 64:
			raise ValueError("Invalid resume token hash")

		try:
			int(resumeTokenHash, 16)
		except ValueError as error:
			raise ValueError("Invalid resume token hash") from error

		return cls(
			playerId=values["playerId"],
			name=values["name"],
			team=values["team"],
			color=values["color"],
			configured=values["configured"],
			resumeTokenHash=resumeTokenHash,
		)

	@classmethod
	def fromSessionPlayer(cls, playerData: dict) -> "PlayerMetadataState":
		return cls(
			playerId=playerData["playerId"],
			name=playerData["name"],
			team=playerData["team"],
			color=playerData["color"],
			configured=playerData["configured"],
			resumeTokenHash=playerData["resumeTokenHash"],
		)


@dataclass(frozen=True, slots=True)
class SessionMetadataState:
	archiveFormatVersion: int
	engineVersion: str
	rulesFormatVersion: int
	sessionId: str
	joinCode: str
	rulesetName: str
	rules: GameRules
	players: tuple[PlayerMetadataState, ...]
	createdAt: datetime
	startedAt: datetime | None
	endedAt: datetime | None
	lastActivityAt: datetime

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
			"players": [player.to_dict() for player in self.players],
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

		players = values.get("players")

		if type(players) is not list:
			raise ValueError("Invalid player metadata list")

		return cls(
			archiveFormatVersion=values["archiveFormatVersion"],
			engineVersion=values["engineVersion"],
			rulesFormatVersion=values["rulesFormatVersion"],
			sessionId=sessionId,
			joinCode=values["joinCode"],
			rulesetName=ruleset["preset"],
			rules=GameRules.from_dict(ruleset["values"]),
			players=tuple(PlayerMetadataState.from_dict(player) for player in players),
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
			rulesetName=session.rulesetName,
			rules=session.rules,
			players=tuple(PlayerMetadataState.fromSessionPlayer(playerData) for playerData in session.players.values()),
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
	