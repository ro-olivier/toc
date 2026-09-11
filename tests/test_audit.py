import json

import pytest

from datetime import datetime, timedelta, timezone

from toc.model.audit import GameEvent, GameEventLog, GameEventType
from main import GameSession, PlayerInputRouter


class FakeClock:
	def __init__(self, initialTime):
		self._utcNow = initialTime
		self._monotonic = 0.0

	def utcNow(self):
		return self._utcNow

	def monotonic(self):
		return self._monotonic

	def advance(self, seconds):
		self._utcNow += timedelta(seconds=seconds)
		self._monotonic += seconds


def test_events_receive_sequence_and_elapsed_time():
	clock = FakeClock(datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc))
	session = GameSession("ABCDEF", PlayerInputRouter(), clock=clock)

	session.markStarted()
	firstEvent = session.recordEvent(GameEventType.GAME_STARTED)

	clock.advance(12)

	secondEvent = session.recordEvent(
		GameEventType.CARD_PLAYED,
		"player-1",
		{
			"card": {"suit": "♥️", "value": "7"},
			"moveType": "MOVE",
			"pieceOwnerId": "player-1",
			"originPositionId": "spot-red-1",
			"targetPositionId": "spot-red-8",
			"steps": 7,
		},
	)

	assert firstEvent.sequence == 1
	assert firstEvent.elapsedSeconds == 0
	assert secondEvent.sequence == 2
	assert secondEvent.elapsedSeconds == 12
	assert secondEvent.playerId == "player-1"
	assert session.lastActivityAt == clock.utcNow()


def test_event_details_are_detached_from_caller():
	details = {
		"deckCycle": 1,
		"deal": 1,
		"cards": [{"suit": "♥️", "value": "7"}],
	}

	event = GameEvent(
		sequence=1,
		elapsedSeconds=0,
		eventType=GameEventType.CARDS_DEALT,
		playerId="player-1",
		details=details,
	)

	details["cards"][0]["value"] = "K"
	details["cards"].append({"suit": "♣️", "value": "A"})

	assert event.details == {
		"deckCycle": 1,
		"deal": 1,
		"cards": [{"suit": "♥️", "value": "7"}],
	}


def test_event_log_survives_json_round_trip():
	elapsedSeconds = 25
	eventLog = GameEventLog(lambda: elapsedSeconds)

	eventLog.record(GameEventType.TURN_STARTED, "player-1", {"handSize": 5})
	eventLog.record(GameEventType.CARD_PLAYED, "player-1", {
		"card": {"suit": "♣️", "value": "K"},
		"moveType": "MOVE",
		"pieceOwnerId": "player-1",
		"originPositionId": "spot-red-1",
		"targetPositionId": "spot-red-14",
		"steps": 13,
	})

	encoded = json.dumps(eventLog.to_list())
	restoredLog = GameEventLog.from_list(json.loads(encoded), lambda: elapsedSeconds)

	assert restoredLog.events == eventLog.events


def test_event_log_rejects_non_contiguous_sequences():
	values = [
		{
			"sequence": 2,
			"elapsedSeconds": 0,
			"type": "game-started",
			"playerId": None,
			"details": {},
		},
	]

	with pytest.raises(ValueError, match="sequence is not contiguous"):
		GameEventLog.from_list(values, lambda: 0)


def test_event_rejects_non_json_details():
	with pytest.raises(ValueError, match="not JSON-compatible"):
		GameEvent(
			sequence=1,
			elapsedSeconds=0,
			eventType=GameEventType.CARD_PLAYED,
			playerId="player-1",
			details={"invalid": object()},
		)

@pytest.mark.parametrize(
	("eventType", "playerId", "details"),
	[
		(GameEventType.TURN_STARTED, "player-1", {}),
		(GameEventType.TURN_STARTED, "player-1", {"handSize": "5"}),
		(GameEventType.PIECE_KICKED, "player-1", {"pieceOwnerId": "player-2", "positionId": "spot-red-7", "reason": "unknown"}),
		(GameEventType.GAME_STARTED, "player-1", {}),
		(GameEventType.TURN_STARTED, None, {"handSize": 5}),
		(GameEventType.CARD_DISCARDED, "player-1", {"reason": "no-legal-move", "card": {"suit": "hearts", "value": "2"}}),
	],
)
def test_event_rejects_invalid_event_specific_data(eventType, playerId, details):
	with pytest.raises(ValueError):
		GameEvent(sequence=1, elapsedSeconds=0, eventType=eventType, playerId=playerId, details=details)