from dataclasses import FrozenInstanceError

import json
import pytest

from rules import *


def test_montsurvent_preset_uses_current_rules():
	assert MONTSURVENT_RULES == GameRules()
	assert MONTSURVENT_RULES.seven_hopping is SevenHopping.OPTIONAL
	assert RULE_PRESETS["montsurvent"] is MONTSURVENT_RULES

def test_game_rules_are_immutable():
	rules = GameRules()

	with pytest.raises(FrozenInstanceError):
		rules.seven_hopping = False


def test_rules_are_serialized_with_json_safe_values():
	rules = GameRules(rotation=Rotation.COUNTERCLOCKWISE, shuffle_cards=ShuffleMode.ON_DEALER_CYCLE, deal_card_counts=(4, 5, 4), ace_values=(11,))

	result = rules.to_dict()

	assert result["rotation"] == "counterclockwise"
	assert result["shuffle_cards"] == "on_dealer_cycle"
	assert result["deal_card_counts"] == [4, 5, 4]
	assert result["ace_values"] == [11]
	json.dumps(result)


def test_rules_can_be_created_from_partial_json_values():
	rules = GameRules.from_dict({"rotation": "counterclockwise", "seven_hopping": "forced", "deal_card_counts": [4, 4, 5], "ace_values": [1]})

	assert rules.rotation is Rotation.COUNTERCLOCKWISE
	assert rules.seven_hopping is SevenHopping.FORCED
	assert rules.deal_card_counts == (4, 4, 5)
	assert rules.ace_values == (1,)
	assert rules.card_exchange is True


def test_rules_round_trip_through_dictionary():
	assert GameRules.from_dict(MONTSURVENT_RULES.to_dict()) == MONTSURVENT_RULES


@pytest.mark.parametrize("values", [
	{"card_exchange": 1},
	{"rotation": "sideways"},
	{"deal_card_counts": [5, 5, 3]},
	{"track_region_length": 17},
	{"track_region_length": 16, "enter_house_at_spot": 18},
	{"ace_values": [1, 2]},
])
def test_invalid_rule_values_are_rejected(values):
	with pytest.raises(ValueError):
		GameRules.from_dict(values)


def test_unknown_rule_field_is_rejected():
	with pytest.raises(ValueError, match="Unknown rule fields: mystery_rule"):
		GameRules.from_dict({"mystery_rule": True})


def test_ruleset_resolver_returns_preset_or_custom_rules():
	assert resolve_ruleset("montsurvent") is MONTSURVENT_RULES

	customRules = resolve_ruleset("custom", {"card_exchange": False})

	assert customRules.card_exchange is False
	assert customRules.rotation is Rotation.CLOCKWISE


@pytest.mark.parametrize(("presetName", "customValues"), [
	("unknown", None),
	("custom", None),
	("montsurvent", {"card_exchange": False}),
])
def test_invalid_ruleset_requests_are_rejected(presetName, customValues):
	with pytest.raises(ValueError):
		resolve_ruleset(presetName, customValues)


def test_rule_schema_describes_every_rule_with_json_safe_options():
	schema = get_rule_schema()

	assert set(schema) == set(MONTSURVENT_RULES.to_dict())
	assert schema["card_exchange"] == {"type": "boolean"}
	assert schema["shuffle_cards"]["options"] == ["never", "on_dealer_change", "on_dealer_cycle"]
	assert schema["deal_card_counts"]["options"] == [[5, 4, 4], [4, 5, 4], [4, 4, 5]]
	assert schema["ace_values"]["options"] == [[1, 11], [1], [11]]
	json.dumps(schema)