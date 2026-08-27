import pytest

from toc.model.game_mode import DEFAULT_GAME_MODE, DuelFourLayout, GameMode, GameModeDefinition, getGameModeDefinition


@pytest.mark.parametrize(
	("mode", "layout", "participantCount", "seatCount", "teamCount", "participantPattern", "teamPattern", "dealCardCounts", "jokerCount"),
	[
		(GameMode.DUEL_TWO, None, 2, 2, 2, (0, 1), (0, 1), (10, 8, 8), 0),
		(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT, 2, 4, 2, (0, 0, 1, 1), (0, 0, 1, 1), (5, 4, 4), 0),
		(GameMode.DUEL_FOUR, DuelFourLayout.CROSS, 2, 4, 2, (0, 1, 0, 1), (0, 1, 0, 1), (5, 4, 4), 0),
		(GameMode.TEAM_FOUR, None, 4, 4, 2, (0, 1, 2, 3), (0, 1, 0, 1), (5, 4, 4), 0),
		(GameMode.TEAM_SIX, None, 6, 6, 3, (0, 1, 2, 3, 4, 5), (0, 1, 2, 0, 1, 2), (3, 3, 3), 2),
	],
)
def test_game_mode_definitions(mode, layout, participantCount, seatCount, teamCount, participantPattern, teamPattern, dealCardCounts, jokerCount):
	definition = getGameModeDefinition(mode, layout)

	assert definition.mode is mode
	assert definition.layout is layout
	assert definition.participantCount == participantCount
	assert definition.seatCount == seatCount
	assert definition.teamCount == teamCount
	assert definition.participantPattern == participantPattern
	assert definition.teamPattern == teamPattern
	assert definition.defaultDealCardCounts == dealCardCounts
	assert definition.jokerCount == jokerCount
	assert definition.participantsPerTeam == participantCount // teamCount
	assert definition.teamIds == tuple(str(teamIndex) for teamIndex in range(teamCount))
	assert len(definition.participantTeamPattern) == participantCount
	assert definition.seatsPerParticipant == seatCount // participantCount


@pytest.mark.parametrize(
	("mode", "layout"),
	[
		(GameMode.DUEL_TWO, None),
		(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT),
		(GameMode.DUEL_FOUR, DuelFourLayout.CROSS),
		(GameMode.TEAM_FOUR, None),
		(GameMode.TEAM_SIX, None),
	],
)
def test_game_mode_dealing_schedule_consumes_complete_deck(mode, layout):
	definition = getGameModeDefinition(mode, layout)

	assert definition.cardsDealtPerCycle == definition.deckCardCount


def test_team_four_remains_default_mode():
	assert DEFAULT_GAME_MODE is GameMode.TEAM_FOUR


def test_game_mode_can_be_resolved_from_strings():
	definition = getGameModeDefinition("duel_four", "cross")

	assert definition.mode is GameMode.DUEL_FOUR
	assert definition.layout is DuelFourLayout.CROSS


def test_duel_four_requires_a_layout():
	with pytest.raises(ValueError, match="requires a layout"):
		getGameModeDefinition(GameMode.DUEL_FOUR)


def test_other_modes_reject_a_duel_four_layout():
	with pytest.raises(ValueError, match="Only duel-four"):
		getGameModeDefinition(GameMode.TEAM_FOUR, DuelFourLayout.CROSS)


def test_unknown_game_mode_is_rejected():
	with pytest.raises(ValueError, match="Unknown game mode"):
		getGameModeDefinition("unknown")

def test_game_mode_definition_survives_dictionary_round_trip():
	originalDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.CROSS)
	restoredDefinition = GameModeDefinition.from_dict(originalDefinition.to_dict())

	assert restoredDefinition == originalDefinition
	assert restoredDefinition.to_dict() == {"name": "duel_four", "layout": "cross"}

@pytest.mark.parametrize(
	("mode", "layout", "expectedSeats"),
	[
		(GameMode.DUEL_TWO, None, 1),
		(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT, 2),
		(GameMode.DUEL_FOUR, DuelFourLayout.CROSS, 2),
		(GameMode.TEAM_FOUR, None, 1),
		(GameMode.TEAM_SIX, None, 1),
	],
)
def test_number_of_seats_per_participant(mode, layout, expectedSeats):
	definition = getGameModeDefinition(mode, layout)

	assert definition.seatsPerParticipant == expectedSeats