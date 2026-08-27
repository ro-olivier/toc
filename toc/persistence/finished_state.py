from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from toc.infrastructure.versions import ARCHIVE_FORMAT_VERSION, ENGINE_VERSION, RULES_FORMAT_VERSION
from toc.model.audit import GameEvent, GameEventType
from toc.model.rules import GameRules
from toc.persistence.snapshot_state import GameState


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
class FinishedPlayerState:
	playerId: str
	name: str
	team: str
	color: str

	def __post_init__(self) -> None:
		_validateId(self.playerId, "finished-player ID")

		if type(self.name) is not str or not self.name:
			raise ValueError("Invalid finished-player name")

		if type(self.team) is not str or not self.team:
			raise ValueError("Invalid finished-player team")

		if type(self.color) is not str or not self.color:
			raise ValueError("Invalid finished-player colour")

	def to_dict(self) -> dict:
		return {
			"playerId": self.playerId,
			"name": self.name,
			"team": self.team,
			"color": self.color,
		}

	@classmethod
	def from_dict(cls, values: dict) -> "FinishedPlayerState":
		if type(values) is not dict or set(values) != {"playerId", "name", "team", "color"}:
			raise ValueError("Invalid finished-player data")

		return cls(
			playerId=values["playerId"],
			name=values["name"],
			team=values["team"],
			color=values["color"],
		)

	@classmethod
	def fromSessionPlayer(cls, playerData: dict) -> "FinishedPlayerState":
		return cls(
			playerId=playerData["playerId"],
			name=playerData["name"],
			team=playerData["team"],
			color=playerData["color"],
		)


@dataclass(frozen=True, slots=True)
class FinishedArchiveState:
	archiveFormatVersion: int
	engineVersion: str
	rulesFormatVersion: int
	sessionId: str
	joinCode: str
	rulesetName: str
	rules: GameRules
	players: tuple[FinishedPlayerState, ...]
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

		if type(self.players) is not tuple or not self.players:
			raise ValueError("Invalid finished-game players")

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

		playerIds = [player.playerId for player in self.players]

		if len(playerIds) != len(set(playerIds)):
			raise ValueError("Finished archive contains duplicate player IDs")

		if len({player.name for player in self.players}) != len(self.players):
			raise ValueError("Finished archive contains duplicate player names")

		if set(playerIds) != set(self.game.playerOrder):
			raise ValueError("Finished archive players do not match game players")

		previousElapsedSeconds = -1

		for expectedSequence, event in enumerate(self.events, start=1):
			if event.sequence != expectedSequence:
				raise ValueError("Finished-game event sequence is not contiguous")

			if event.elapsedSeconds < previousElapsedSeconds:
				raise ValueError("Finished-game event elapsed times are not ordered")

			if event.playerId is not None and event.playerId not in playerIds:
				raise ValueError("Finished-game event references an unknown player")

			previousElapsedSeconds = event.elapsedSeconds

		if self.events[-1].eventType is not GameEventType.GAME_FINISHED:
			raise ValueError("Finished archive must end with a game-finished event")

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
			"players",
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

		if type(values["players"]) is not list:
			raise ValueError("Invalid finished-game players")

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
			players=tuple(FinishedPlayerState.from_dict(player) for player in values["players"]),
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
			players=tuple(FinishedPlayerState.fromSessionPlayer(playerData) for playerData in session.players.values()),
			createdAt=session.createdAt,
			startedAt=session.startedAt,
			endedAt=session.endedAt,
			game=GameState.fromGameSession(session),
			events=session.events,
		)