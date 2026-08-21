import pytest
import ast
from pathlib import Path

from messages import MESSAGE_KEYS, build_message



def test_build_message_contains_translation_and_event_data():
	message = build_message("play", "gameplay.piece_moved", "Alice played ♥️5.", {"player": "Alice", "card": "♥️5"}, playerId="Alice", value="5", suit="♥️")

	assert message == {
		"type": "play",
		"messageKey": "gameplay.piece_moved",
		"parameters": {"player": "Alice", "card": "♥️5"},
		"fallback": "Alice played ♥️5.",
		"playerId": "Alice",
		"value": "5",
		"suit": "♥️",
	}


def test_build_message_uses_independent_empty_parameters():
	firstMessage = build_message("log", "gameplay.game_starting", "The game started.")
	secondMessage = build_message("log", "gameplay.game_starting", "The game started.")

	firstMessage["parameters"]["test"] = True

	assert secondMessage["parameters"] == {}


def test_build_message_rejects_old_msg_field():
	with pytest.raises(ValueError, match="Reserved message fields"):
		build_message("log", "gameplay.game_starting", "The game started.", msg="Old message")

def test_every_backend_message_key_is_registered():
	projectRoot = Path(__file__).resolve().parents[1]
	messageKeyPrefixes = ("connection.", "errors.", "gameplay.", "lobby.errors.", "prompts.")
	sourceKeys = set()

	for filename in ["main.py", "game.py", "player.py"]:
		tree = ast.parse((projectRoot / filename).read_text(encoding="utf-8"))

		for node in ast.walk(tree):
			if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
				continue

			if node.value.startswith(messageKeyPrefixes) and not any(character.isspace() for character in node.value):
				sourceKeys.add(node.value)

	assert sourceKeys == set(MESSAGE_KEYS)