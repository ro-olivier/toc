import json

from datetime import datetime, timedelta, timezone

from main import ConnectionManager, GameSession, PlayerInputRouter
from toc.persistence.persistent_state import SessionMetadataState


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


def test_game_session_uses_injected_clock():
	initialTime = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
	clock = FakeClock(initialTime)
	session = GameSession("ABCDEF", PlayerInputRouter(), clock=clock)

	assert session.createdAt == initialTime
	assert session.lastActivityAt == initialTime
	assert session.startedAt is None
	assert session.endedAt is None

	clock.advance(300)

	assert session.lobbyAgeSeconds() == 300
	assert session.inactivitySeconds() == 300

	session.recordActivity()

	assert session.lastActivityAt == initialTime + timedelta(seconds=300)
	assert session.inactivitySeconds() == 0

	clock.advance(60)
	session.markStarted()

	assert session.started
	assert session.startedAt == initialTime + timedelta(seconds=360)
	assert session.lastActivityAt == session.startedAt
	assert session.inactivitySeconds() == 0

	clock.advance(20)
	session.recordActivity()

	assert session.lastActivityAt == initialTime + timedelta(seconds=380)

	clock.advance(10)
	session.markEnded()

	assert session.endedAt == initialTime + timedelta(seconds=390)
	assert session.lastActivityAt == session.endedAt


def test_connection_manager_passes_clock_to_new_session():
	initialTime = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
	clock = FakeClock(initialTime)
	connectionManager = ConnectionManager(clock)
	gameId = connectionManager.create_game(PlayerInputRouter())
	session = connectionManager.get_game(gameId)

	assert session.createdAt == initialTime

	clock.advance(15)

	assert session.lobbyAgeSeconds() == 15


def test_session_timestamps_survive_json_round_trip():
	initialTime = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
	clock = FakeClock(initialTime)
	session = GameSession("ABCDEF", PlayerInputRouter(), clock=clock)

	clock.advance(30)
	session.markStarted()

	clock.advance(45)
	session.recordActivity()

	clock.advance(15)
	session.markEnded()

	originalState = session.metadataState()
	encoded = json.dumps(originalState.to_dict())
	restoredState = SessionMetadataState.from_dict(json.loads(encoded))

	assert restoredState == originalState
	assert restoredState.createdAt == initialTime
	assert restoredState.startedAt == initialTime + timedelta(seconds=30)
	assert restoredState.lastActivityAt == initialTime + timedelta(seconds=90)
	assert restoredState.endedAt == initialTime + timedelta(seconds=90)