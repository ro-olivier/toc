from dataclasses import dataclass
from enum import StrEnum


class GameMode(StrEnum):
	DUEL_TWO = "duel_two"
	DUEL_FOUR = "duel_four"
	TEAM_FOUR = "team_four"
	TEAM_SIX = "team_six"


class DuelFourLayout(StrEnum):
	ADJACENT = "adjacent"
	CROSS = "cross"


@dataclass(frozen=True, slots=True)
class GameModeDefinition:
	mode: GameMode
	layout: DuelFourLayout | None
	participantCount: int
	seatCount: int
	teamCount: int
	participantPattern: tuple[int, ...]
	teamPattern: tuple[int, ...]
	defaultDealCardCounts: tuple[int, ...]
	jokerCount: int = 0

	def __post_init__(self) -> None:
		if not isinstance(self.mode, GameMode):
			raise ValueError("Invalid game mode")

		if self.mode is GameMode.DUEL_FOUR and not isinstance(self.layout, DuelFourLayout):
			raise ValueError("Duel-four mode requires a layout")

		if self.mode is not GameMode.DUEL_FOUR and self.layout is not None:
			raise ValueError("Only duel-four mode may define a layout")

		if type(self.participantCount) is not int or self.participantCount < 2:
			raise ValueError("A game mode must have at least two participants")

		if type(self.seatCount) is not int or self.seatCount < 2:
			raise ValueError("A game mode must have at least two seats")

		if type(self.teamCount) is not int or self.teamCount < 2:
			raise ValueError("A game mode must have at least two teams")

		if self.participantCount % self.teamCount != 0:
			raise ValueError("Participants must be distributed equally between teams")

		if type(self.participantPattern) is not tuple or len(self.participantPattern) != self.seatCount:
			raise ValueError("Participant pattern must contain one entry per seat")

		if set(self.participantPattern) != set(range(self.participantCount)):
			raise ValueError("Participant pattern does not match participant count")

		if type(self.teamPattern) is not tuple or len(self.teamPattern) != self.seatCount:
			raise ValueError("Team pattern must contain one entry per seat")

		if set(self.teamPattern) != set(range(self.teamCount)):
			raise ValueError("Team pattern does not match team count")

		participantTeams = {}

		for participantIndex, teamIndex in zip(self.participantPattern, self.teamPattern):
			if participantIndex in participantTeams and participantTeams[participantIndex] != teamIndex:
				raise ValueError("A participant cannot control seats from different teams")

			participantTeams[participantIndex] = teamIndex

		seatCountsByParticipant = tuple(self.participantPattern.count(participantIndex) for participantIndex in range(self.participantCount))

		if len(set(seatCountsByParticipant)) != 1:
			raise ValueError("All participants must control the same number of seats")

		if type(self.defaultDealCardCounts) is not tuple or not self.defaultDealCardCounts:
			raise ValueError("A game mode must define its dealing schedule")

		if any(type(cardCount) is not int or cardCount <= 0 for cardCount in self.defaultDealCardCounts):
			raise ValueError("Deal card counts must be positive integers")

		if type(self.jokerCount) is not int or self.jokerCount < 0:
			raise ValueError("Joker count cannot be negative")

		if self.cardsDealtPerCycle != self.deckCardCount:
			raise ValueError("Dealing schedule does not consume the complete deck")

	@property
	def deckCardCount(self) -> int:
		return 52 + self.jokerCount

	@property
	def cardsDealtPerCycle(self) -> int:
		return self.seatCount * sum(self.defaultDealCardCounts)

	@property
	def participantsPerTeam(self) -> int:
		return self.participantCount // self.teamCount

	@property
	def teamIds(self) -> tuple[str, ...]:
		return tuple(str(teamIndex) for teamIndex in range(self.teamCount))

	def to_dict(self) -> dict:
		return {
			"name": self.mode.value,
			"layout": self.layout.value if self.layout is not None else None,
		}

	@property
	def participantTeamPattern(self) -> tuple[int, ...]:
		participantTeams = [None] * self.participantCount

		for participantIndex, teamIndex in zip(self.participantPattern, self.teamPattern):
			participantTeams[participantIndex] = teamIndex

		return tuple(participantTeams)

	@property
	def seatsPerParticipant(self) -> int:
		return self.seatCount // self.participantCount

	@classmethod
	def from_dict(cls, values: dict) -> "GameModeDefinition":
		if type(values) is not dict or set(values) != {"name", "layout"}:
			raise ValueError("Invalid game-mode definition")

		try:
			definition = getGameModeDefinition(values["name"], values["layout"])
		except ValueError as error:
			raise ValueError("Invalid game-mode definition") from error

		if not isinstance(definition, cls):
			raise ValueError("Invalid game-mode definition")

		return definition

	def resolveDealCardCounts(self, configuredDealCardCounts: tuple[int, ...]) -> tuple[int, ...]:
		if type(configuredDealCardCounts) is not tuple or not configuredDealCardCounts:
			raise ValueError("Configured dealing schedule must be a non-empty tuple")

		if any(type(cardCount) is not int or cardCount <= 0 for cardCount in configuredDealCardCounts):
			raise ValueError("Configured deal card counts must be positive integers")

		if self.seatCount * sum(configuredDealCardCounts) == self.deckCardCount:
			return configuredDealCardCounts

		return self.defaultDealCardCounts


DEFAULT_GAME_MODE = GameMode.TEAM_FOUR


_MODE_DEFINITIONS = {
	(GameMode.DUEL_TWO, None): GameModeDefinition(
		mode=GameMode.DUEL_TWO,
		layout=None,
		participantCount=2,
		seatCount=2,
		teamCount=2,
		participantPattern=(0, 1),
		teamPattern=(0, 1),
		defaultDealCardCounts=(10, 8, 8),
	),
	(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT): GameModeDefinition(
		mode=GameMode.DUEL_FOUR,
		layout=DuelFourLayout.ADJACENT,
		participantCount=2,
		seatCount=4,
		teamCount=2,
		participantPattern=(0, 0, 1, 1),
		teamPattern=(0, 0, 1, 1),
		defaultDealCardCounts=(5, 4, 4),
	),
	(GameMode.DUEL_FOUR, DuelFourLayout.CROSS): GameModeDefinition(
		mode=GameMode.DUEL_FOUR,
		layout=DuelFourLayout.CROSS,
		participantCount=2,
		seatCount=4,
		teamCount=2,
		participantPattern=(0, 1, 0, 1),
		teamPattern=(0, 1, 0, 1),
		defaultDealCardCounts=(5, 4, 4),
	),
	(GameMode.TEAM_FOUR, None): GameModeDefinition(
		mode=GameMode.TEAM_FOUR,
		layout=None,
		participantCount=4,
		seatCount=4,
		teamCount=2,
		participantPattern=(0, 1, 2, 3),
		teamPattern=(0, 1, 0, 1),
		defaultDealCardCounts=(5, 4, 4),
	),
	(GameMode.TEAM_SIX, None): GameModeDefinition(
		mode=GameMode.TEAM_SIX,
		layout=None,
		participantCount=6,
		seatCount=6,
		teamCount=3,
		participantPattern=(0, 1, 2, 3, 4, 5),
		teamPattern=(0, 1, 2, 0, 1, 2),
		defaultDealCardCounts=(3, 3, 3),
		jokerCount=2,
	),
}


def getGameModeDefinition(mode: GameMode | str, layout: DuelFourLayout | str | None = None) -> GameModeDefinition:
	try:
		mode = GameMode(mode)
	except (TypeError, ValueError) as error:
		raise ValueError(f"Unknown game mode: {mode}") from error

	if mode is not GameMode.DUEL_FOUR:
		if layout is not None:
			raise ValueError("Only duel-four mode accepts a layout")

		return _MODE_DEFINITIONS[(mode, None)]

	if layout is None:
		raise ValueError("Duel-four mode requires a layout")

	try:
		layout = DuelFourLayout(layout)
	except (TypeError, ValueError) as error:
		raise ValueError(f"Unknown duel-four layout: {layout}") from error

	return _MODE_DEFINITIONS[(mode, layout)]