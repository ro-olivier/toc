from __future__ import annotations

import asyncio
import logging
from typing import Dict

from settings import GAME_SUSPENDED_CLOSE_CODE, LOBBY_EXPIRED_CLOSE_CODE, LOBBY_LIFETIME_SECONDS, SESSION_MONITOR_INTERVAL_SECONDS
from toc.infrastructure.clock import Clock, SYSTEM_CLOCK
from toc.infrastructure.identity import createJoinCode, normalizeJoinCode
from toc.model.game_mode import GameModeDefinition
from toc.model.rules import GameRules, MONTSURVENT_RULES
from toc.persistence.archive_store import ArchiveCategory, ArchiveCorruptionError, CompressedJsonStore
from toc.persistence.snapshot_state import SessionSnapshotState
from toc.session.game_session import GameSession
from toc.session.input_router import PlayerInputRouter


logger = logging.getLogger("toc.main")


class ConnectionManager:
	def __init__(self, clock: Clock = SYSTEM_CLOCK, archiveStore: CompressedJsonStore = None):
		self.games: Dict[str, GameSession] = {}
		self._clock = clock
		self._archiveStore = archiveStore

	def _generate_game_id(self) -> str:
		reservedJoinCodes = {normalizeJoinCode(joinCode) for joinCode in self.games}
		reservedJoinCodes.update(self._get_suspended_join_codes())

		while True:
			gameId = normalizeJoinCode(createJoinCode())

			if gameId not in reservedJoinCodes:
				return gameId

	def create_game(self, msg_router, rules: GameRules = MONTSURVENT_RULES, rulesetName: str = None, modeDefinition: GameModeDefinition = None, creatorName: str = "") -> str:
		game_id = self._generate_game_id()
		self.games[game_id] = GameSession(game_id, msg_router, rules, rulesetName, self._clock, self._archiveStore, modeDefinition, creatorName)
		return game_id

	def get_game(self, game_id: str):
		try:
			normalizedGameId = normalizeJoinCode(game_id)
		except ValueError:
			return None

		return self.games.get(normalizedGameId) or self.games.get(game_id)

	def _get_suspended_join_codes(self) -> set[str]:
		if self._archiveStore is None:
			return set()

		joinCodes = set()

		for sessionId in self._archiveStore.listDocumentIds(ArchiveCategory.SUSPENDED):
			try:
				payload = self._archiveStore.read(ArchiveCategory.SUSPENDED, sessionId)
				snapshot = SessionSnapshotState.from_dict(payload)
				joinCodes.add(normalizeJoinCode(snapshot.metadata.joinCode))
			except (ArchiveCorruptionError, ValueError):
				logger.exception("Could not read suspended game join code", extra={"sessionId": sessionId})

		return joinCodes

	def get_open_lobbies(self) -> list[dict]:
		lobbies = []

		for session in reversed(tuple(self.games.values())):
			if session.started or session.is_full():
				continue

			if session.lobbyAgeSeconds() >= LOBBY_LIFETIME_SECONDS:
				continue

			lobbies.append({
				"gameName": session.joinCode,
				"creatorName": session.creatorName,
				"playerCount": len(session.participants),
				"playerCapacity": session.modeDefinition.participantCount,
				"mode": session.modeDefinition.to_dict(),
			})

		return lobbies

	def load_suspended_game(self, game_id: str, msg_router) -> GameSession | None:
		if self._archiveStore is None:
			return None

		matchingSnapshots = []

		for sessionId in self._archiveStore.listDocumentIds(ArchiveCategory.SUSPENDED):
			try:
				payload = self._archiveStore.read(ArchiveCategory.SUSPENDED, sessionId)
				snapshot = SessionSnapshotState.from_dict(payload)
			except (ArchiveCorruptionError, ValueError):
				logger.exception("Could not load suspended game archive", extra={"sessionId": sessionId})
				continue

			normalizedGameId = normalizeJoinCode(game_id)
			if normalizeJoinCode(snapshot.metadata.joinCode) == normalizedGameId:
				matchingSnapshots.append(snapshot)

		if not matchingSnapshots:
			return None

		if len(matchingSnapshots) > 1:
			raise RuntimeError(f"Multiple suspended archives use join code '{game_id}'")

		snapshot = matchingSnapshots[0]

		if not snapshot.game.isStarted:
			raise ValueError("Suspended archive contains an unstarted game")

		if snapshot.game.isFinished:
			raise ValueError("Suspended archive contains a finished game")

		session = GameSession.fromSnapshot(snapshot, msg_router, self._clock, self._archiveStore)
		self.games[normalizedGameId] = session
		return session

	def get_or_restore_game(self, game_id: str, msg_router) -> GameSession | None:
		existingSession = self.get_game(game_id)

		if existingSession is not None:
			return existingSession

		return self.load_suspended_game(game_id, msg_router)

	async def recover_interrupted_games(self) -> dict:
		if self._archiveStore is None:
			return {"suspended": (), "finished": (), "failed": ()}

		suspendedSessionIds = []
		finishedSessionIds = []
		failedSessionIds = []

		for sessionId in self._archiveStore.listDocumentIds(ArchiveCategory.ACTIVE):
			try:
				activePayload = await asyncio.to_thread(self._archiveStore.read, ArchiveCategory.ACTIVE, sessionId)
				activeSnapshot = SessionSnapshotState.from_dict(activePayload)

				if activeSnapshot.metadata.sessionId != sessionId:
					raise ValueError("Active archive filename does not match its session ID")

			except (ArchiveCorruptionError, ValueError, OSError):
				logger.exception("Could not recover active game archive", extra={"sessionId": sessionId})
				failedSessionIds.append(sessionId)
				continue

			candidates = [(ArchiveCategory.ACTIVE, activeSnapshot, activePayload)]
			suspendedPath = self._archiveStore.pathFor(ArchiveCategory.SUSPENDED, sessionId)

			if suspendedPath.exists():
				try:
					suspendedPayload = await asyncio.to_thread(self._archiveStore.read, ArchiveCategory.SUSPENDED, sessionId)
					suspendedSnapshot = SessionSnapshotState.from_dict(suspendedPayload)

					if suspendedSnapshot.metadata.sessionId != sessionId:
						raise ValueError("Suspended archive filename does not match its session ID")

					candidates.append((ArchiveCategory.SUSPENDED, suspendedSnapshot, suspendedPayload))

				except (ArchiveCorruptionError, ValueError, OSError):
					logger.warning("Ignoring invalid duplicate suspended archive", exc_info=True, extra={"sessionId": sessionId})

			selectedCategory, selectedSnapshot, selectedPayload = max(
				candidates,
				key=lambda candidate: (
					candidate[1].metadata.lastActivityAt,
					candidate[0] is ArchiveCategory.ACTIVE,
				),
			)

			try:
				if selectedSnapshot.game.isFinished:
					recoveryRouter = PlayerInputRouter()
					session = GameSession.fromSnapshot(selectedSnapshot, recoveryRouter, self._clock, self._archiveStore)
					await session.finalizeFinishedGame()
					finishedSessionIds.append(sessionId)
					continue

				if selectedCategory is ArchiveCategory.ACTIVE:
					def moveActiveToSuspended():
						self._archiveStore.write(ArchiveCategory.SUSPENDED, sessionId, selectedPayload)
						self._archiveStore.delete(ArchiveCategory.ACTIVE, sessionId)

					await asyncio.to_thread(moveActiveToSuspended)

				else:
					await asyncio.to_thread(self._archiveStore.delete, ArchiveCategory.ACTIVE, sessionId)

				suspendedSessionIds.append(sessionId)

			except (ValueError, OSError):
				logger.exception("Could not complete interrupted-game recovery", extra={"sessionId": sessionId})
				failedSessionIds.append(sessionId)

		return {
			"suspended": tuple(suspendedSessionIds),
			"finished": tuple(finishedSessionIds),
			"failed": tuple(failedSessionIds),
		}

	async def monitor_sessions(self, intervalSeconds: float = SESSION_MONITOR_INTERVAL_SECONDS) -> None:
		while True:
			await asyncio.sleep(intervalSeconds)
			await self.monitor_once()

	async def monitor_once(self) -> dict:
		expiredGameIds = []
		suspendedGameIds = []
		failedGameIds = []

		for gameId, session in list(self.games.items()):
			try:
				if session.lobbyHasExpired():
					await session.closeConnections(LOBBY_EXPIRED_CLOSE_CODE, "Lobby expired")

					if self.games.get(gameId) is session:
						self.games.pop(gameId)

					expiredGameIds.append(gameId)
					continue

				suspensionReason = session.getSuspensionReason()

				if suspensionReason is None:
					continue

				await session.suspendGame()
				await session.closeConnections(GAME_SUSPENDED_CLOSE_CODE, "Game suspended")

				if self.games.get(gameId) is session:
					self.games.pop(gameId)

				suspendedGameIds.append(gameId)

				logger.info(
					"Game suspended",
					extra={
						"sessionId": session.sessionId,
						"joinCode": session.joinCode,
						"suspensionReason": suspensionReason,
					},
				)

			except Exception:
				logger.exception("Session timeout action failed", extra={"joinCode": gameId})
				failedGameIds.append(gameId)

		return {
			"expired": tuple(expiredGameIds),
			"suspended": tuple(suspendedGameIds),
			"failed": tuple(failedGameIds),
		}
