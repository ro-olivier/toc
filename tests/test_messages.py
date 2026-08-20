import pytest

from messages import build_message


def test_build_message_contains_translation_and_event_data():
	message = build_message("play", "gameplay.card_played", "Alice played ♥️5.", {"player": "Alice", "card": "♥️5"}, playerId="Alice", value="5", suit="♥️")

	assert message == {
		"type": "play",
		"messageKey": "gameplay.card_played",
		"parameters": {"player": "Alice", "card": "♥️5"},
		"fallback": "Alice played ♥️5.",
		"playerId": "Alice",
		"value": "5",
		"suit": "♥️",
	}


def test_build_message_uses_independent_empty_parameters():
	firstMessage = build_message("log", "gameplay.started", "The game started.")
	secondMessage = build_message("log", "gameplay.started", "The game started.")

	firstMessage["parameters"]["test"] = True

	assert secondMessage["parameters"] == {}


def test_build_message_rejects_old_msg_field():
	with pytest.raises(ValueError, match="Reserved message fields"):
		build_message("log", "gameplay.started", "The game started.", msg="Old message")