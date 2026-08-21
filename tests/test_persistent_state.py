import json

import pytest

from identity import createPlayerId, createResumeToken, hashResumeToken
from main import GameSession, PlayerInputRouter
from persistent_state import SessionMetadataState
from versions import ARCHIVE_FORMAT_VERSION, ENGINE_VERSION, RULES_FORMAT_VERSION


def makeSessionWithPlayer():
	session = GameSession("ABCDEF", PlayerInputRouter())
	resumeToken = createResumeToken()

	session.players["ABCDEF-Alice"] = {
		"name": "Alice",
		"id": "ABCDEF-Alice",
		"playerId": createPlayerId(),
		"resumeTokenHash": hashResumeToken(resumeToken),
		"websocket": object(),
		"team": "0",
		"color": "red",
		"object": object(),
		"active": True,
		"configured": True,
	}

	return session, resumeToken


def test_session_metadata_contains_only_persistent_data():
	session, resumeToken = makeSessionWithPlayer()

	state = session.metadataState()
	payload = state.to_dict()
	encoded = json.dumps(payload)

	assert payload["archiveFormatVersion"] == ARCHIVE_FORMAT_VERSION
	assert payload["engineVersion"] == ENGINE_VERSION
	assert payload["rulesFormatVersion"] == RULES_FORMAT_VERSION
	assert payload["sessionId"] == session.sessionId
	assert payload["joinCode"] == "ABCDEF"

	assert payload["players"][0]["name"] == "Alice"
	assert payload["players"][0]["team"] == "0"
	assert payload["players"][0]["color"] == "red"

	assert "websocket" not in payload["players"][0]
	assert "object" not in payload["players"][0]
	assert "active" not in payload["players"][0]
	assert resumeToken not in encoded


def test_session_metadata_survives_json_round_trip():
	session, _ = makeSessionWithPlayer()

	originalState = session.metadataState()
	encoded = json.dumps(originalState.to_dict())
	restoredState = SessionMetadataState.from_dict(json.loads(encoded))

	assert restoredState == originalState
	assert restoredState.rules == session.rules
	assert restoredState.players == originalState.players


def test_unknown_archive_format_is_rejected():
	session, _ = makeSessionWithPlayer()
	payload = session.metadataState().to_dict()
	payload["archiveFormatVersion"] = 999

	with pytest.raises(ValueError, match="Unsupported archive format version"):
		SessionMetadataState.from_dict(payload)


def test_unknown_rules_format_is_rejected():
	session, _ = makeSessionWithPlayer()
	payload = session.metadataState().to_dict()
	payload["rulesFormatVersion"] = 999

	with pytest.raises(ValueError, match="Unsupported rules format version"):
		SessionMetadataState.from_dict(payload)