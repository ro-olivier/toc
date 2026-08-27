import json
import logging

from toc.infrastructure.app_logging import TocJsonFormatter


def test_json_formatter_includes_structured_context():
	record = logging.LogRecord(
		name="toc.test",
		level=logging.INFO,
		pathname=__file__,
		lineno=10,
		msg="Player connected",
		args=(),
		exc_info=None,
	)

	record.sessionId = "session-123"
	record.joinCode = "ABCDEF"
	record.playerId = "player-456"
	record.playerName = "Alice"
	record.event = "player-connected"

	payload = json.loads(TocJsonFormatter().format(record))

	assert payload["level"] == "INFO"
	assert payload["logger"] == "toc.test"
	assert payload["message"] == "Player connected"
	assert payload["sessionId"] == "session-123"
	assert payload["joinCode"] == "ABCDEF"
	assert payload["playerId"] == "player-456"
	assert payload["playerName"] == "Alice"
	assert payload["event"] == "player-connected"
	assert payload["timestamp"].endswith("+00:00")


def test_json_formatter_omits_context_that_was_not_provided():
	record = logging.LogRecord(
		name="toc.test",
		level=logging.WARNING,
		pathname=__file__,
		lineno=10,
		msg="Something happened",
		args=(),
		exc_info=None,
	)

	payload = json.loads(TocJsonFormatter().format(record))

	assert payload["message"] == "Something happened"
	assert "sessionId" not in payload
	assert "playerId" not in payload