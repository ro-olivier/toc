from dataclasses import FrozenInstanceError

import pytest

from rules import GameRules, MONTSURVENT_RULES, RULE_PRESETS, SevenHopping


def test_montsurvent_preset_uses_current_rules():
	assert MONTSURVENT_RULES == GameRules()
	assert MONTSURVENT_RULES.seven_hopping is SevenHopping.OPTIONAL
	assert RULE_PRESETS["montsurvent"] is MONTSURVENT_RULES

def test_game_rules_are_immutable():
	rules = GameRules()

	with pytest.raises(FrozenInstanceError):
		rules.seven_hopping = False
