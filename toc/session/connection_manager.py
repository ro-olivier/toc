from __future__ import annotations

import asyncio
import logging

from toc.infrastructure.clock import Clock, SYSTEM_CLOCK
from toc.infrastructure.identity import createJoinCode, normalizeJoinCode
from toc.model.game_mode import GameModeDefinition
from toc.model.rules import GameRules, MONTSURVENT_RULES
from toc.persistence.archive_store import ArchiveCategory, ArchiveCorruptionError, CompressedJsonStore
from toc.persistence.snapshot_state import SessionSnapshotState
from toc.session.game_session import GameSession
from toc.session.input_router import PlayerInputRouter
from settings import GAME_SUSPENDED_CLOSE_CODE, LOBBY_EXPIRED_CLOSE_CODE, LOBBY_LIFETIME_SECONDS, SESSION_MONITOR_INTERVAL_SECONDS


logger = logging.getLogger("toc.main")


class ConnectionManager:
	def __init__(self, clock: Clock = SYSTEM_CLOCK, archiveStore: CompressedJsonStore | None = None) -> None:
		self.games: dict[str, GameSession] = {}
		self._clock = clock
		self._archiveStore: CompressedJsonStore | None = archiveStore

	def _generateGameId(self) -> str:
		reservedJoinCodes = {normalizeJoinCode(joinCode) for joinCode in self.games}
		reservedJoinCodes.update(self._getSuspendedJoinCodes())

		while True:
			gameId = normalizeJoinCode(createJoinCode())

			if gameId not in reservedJoinCodes:
				return gameId

	def createGame(self, msg_router: PlayerInputRouter, rules: GameRules = MONTSURVENT_RULES, rulesetName: str | None = None, modeDefinition: GameModeDefinition | None = None, creatorName: str = "") -> str:
		gameId = self._generateGameId()
		self.games[gameId] = GameSession(gameId, msg_router, rules, rulesetName, self._clock, self._archiveStore, modeDefinition, creatorName)
		return gameId

	def getGame(self, gameId: str) -> GameSession | None:
		try:
			normalizedGameId = normalizeJoinCode(gameId)
		except ValueError:
			return None

		return self.games.get(normalizedGameId) or self.games.get(gameId)

	def _getSuspendedJoinCodes(self) -> set[str]:
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

	def getOpenLobbies(self) -> list[dict[str, object]]:
		lobbies: list[dict[str, object]] = []

		for session in reversed(tuple(self.games.values())):
			if session.started or session.isFull():
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

	def _loadSuspendedGame(self, gameId: str, msg_router: PlayerInputRouter) -> GameSession | None:
		if self._archiveStore is None:
			return None

		matchingSnapshots: list[SessionSnapshotState] = []

		for sessionId in self._archiveStore.listDocumentIds(ArchiveCategory.SUSPENDED):
			try:
				payload = self._archiveStore.read(ArchiveCategory.SUSPENDED, sessionId)
				snapshot = SessionSnapshotState.from_dict(payload)
			except (ArchiveCorruptionError, ValueError):
				logger.exception("Could not load suspended game archive", extra={"sessionId": sessionId})
				continue

			normalizedGameId = normalizeJoinCode(gameId)
			if normalizeJoinCode(snapshot.metadata.joinCode) == normalizedGameId:
				matchingSnapshots.append(snapshot)

		if not matchingSnapshots:
			return None

		if len(matchingSnapshots) > 1:
			raise RuntimeError(f"Multiple suspended archives use join code '{gameId}'")

		snapshot = matchingSnapshots[0]

		if not snapshot.game.isStarted:
			raise ValueError("Suspended archive contains an unstarted game")

		if snapshot.game.isFinished:
			raise ValueError("Suspended archive contains a finished game")

		session = GameSession.fromSnapshot(snapshot, msg_router, self._clock, self._archiveStore)
		self.games[normalizedGameId] = session
		return session

	def getOrRestoreGame(self, gameId: str, msg_router: PlayerInputRouter) -> GameSession | None:
		existingSession = self.getGame(gameId)

		if existingSession is not None:
			return existingSession

		return self._loadSuspendedGame(gameId, msg_router)

	async def recoverInterruptedGames(self) -> dict[str, tuple[str, ...]]:
		if self._archiveStore is None:
			return {"suspended": (), "finished": (), "failed": ()}

		suspendedSessionIds: list[str] = []
		finishedSessionIds: list[str] = []
		failedSessionIds: list[str] = []

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
					def moveActiveToSuspended() -> None:
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

	async def monitorSessions(self, intervalSeconds: float = SESSION_MONITOR_INTERVAL_SECONDS) -> None:
		while True:
			await asyncio.sleep(intervalSeconds)
			await self.monitorOnce()

	async def monitorOnce(self) -> dict[str, tuple[str, ...]]:
		expiredGameIds: list[str] = []
		suspendedGameIds: list[str] = []
		failedGameIds: list[str] = []

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
