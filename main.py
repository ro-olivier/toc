from __future__ import annotations

from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import json
import logging
import uuid
import os
from contextlib import asynccontextmanager, suppress

from settings import *
from toc.model.game import Game
from toc.model.player import Player
from toc.model.params import *
from toc.model.rules import *
from toc.model.move import Move
from toc.model.game_phase import GamePhase
from toc.model.audit import GameEvent, GameEventLog, GameEventType
from toc.infrastructure.messages import MESSAGE_KEYS, build_message
from toc.infrastructure.identity import createJoinCode, createPlayerId, createResumeToken, createSessionId, hashResumeToken, resumeTokenMatches
from toc.infrastructure.versions import WEBSOCKET_PROTOCOL_VERSION
from toc.infrastructure.clock import Clock, SYSTEM_CLOCK
from toc.infrastructure.app_logging import configureApplicationLogging
from toc.persistence.persistent_state import SessionMetadataState
from toc.persistence.snapshot_state import CardState, GameProgressState, SessionSnapshotState, SevenHopProgressState, SevenSplitProgressState
from toc.persistence.archive_store import ArchiveCategory, ArchiveCorruptionError, CompressedJsonStore
from toc.persistence.finished_state import FinishedArchiveState

configureApplicationLogging()
logger = logging.getLogger("toc.main")

@asynccontextmanager
async def applicationLifespan(app: FastAPI):
	recoveryResult = await manager.recover_interrupted_games()

	logger.info(
		"Interrupted-game recovery completed",
		extra={
			"suspendedCount": len(recoveryResult["suspended"]),
			"finishedCount": len(recoveryResult["finished"]),
			"failedCount": len(recoveryResult["failed"]),
		},
	)

	monitorTask = asyncio.create_task(manager.monitor_sessions())

	try:
		yield
	finally:
		monitorTask.cancel()

		with suppress(asyncio.CancelledError):
			await monitorTask
app = FastAPI(lifespan=applicationLifespan)
app.mount(
	"/toc/play",
	StaticFiles(directory=BASE_DIR / "web", html=True),
	name="toc-frontend",
)

class DuplicateNameError(Exception):
	pass

class PlayerInputRouter:
	def __init__(self):
		self.input_queues = {}
		self.output_queues = {}
		self.recycleBin = {}
		self.pendingPrompts = {}
		self.interactiveMessageTypes = {"query-card", "query-card-exchange", "query-origin", "query-target", "query-seven-hop"}

	def register(self, player_name: str):
		if player_name in self.input_queues:
			logger.info("Attempted to re-registered a user with same name", extra={"routerId": player_name})
			raise DuplicateNameError
		else:
			logger.info("Player registered with router", extra={"routerId": player_name})
			self.input_queues[player_name] = asyncio.Queue()
			self.output_queues[player_name] = asyncio.Queue()

	def registerAgain(self, player_name: str):
		logger.info("Player re-registered with router", extra={"routerId": player_name})
		queues = self.recycleBin.pop(player_name)
		self.input_queues[player_name] = queues["in"]
		self.output_queues[player_name] = queues["out"]

	def unregister(self, player_name: str):
		if player_name not in self.input_queues:
			return

		logger.info("Player unregistered from router", extra={"routerId": player_name})
		self.recycleBin[player_name] = {
			"in": self.input_queues.pop(player_name),
			"out": self.output_queues.pop(player_name),
		}

	def prepareDisconnectedPlayer(self, player_name: str) -> None:
		self.input_queues.pop(player_name, None)
		self.output_queues.pop(player_name, None)
		self.recycleBin.pop(player_name, None)
		self.pendingPrompts.pop(player_name, None)

		self.recycleBin[player_name] = {
			"in": asyncio.Queue(),
			"out": asyncio.Queue(),
		}

	async def add_input(self, player_name: str, message: str):
		messageType = message.get("type") if isinstance(message, dict) else type(message).__name__
		logger.debug("Player input queued", extra={"routerId": player_name, "messageType": messageType})
		queue = self.input_queues.get(player_name)
		if queue:
			await queue.put(message)
		else:
			logger.warning("No input queue found", extra={"routerId": player_name})

	async def wait_for_input(self, player_name: str):
		while True:
			msg = await self.input_queues[player_name].get()
			pendingPrompt = self.pendingPrompts.get(player_name)

			if pendingPrompt is None:
				return msg

			requestId = msg.get("requestId") if isinstance(msg, dict) else None

			if requestId is None or requestId == pendingPrompt.get("requestId"):
				return msg

			logger.info("Ignored stale player input", extra={"routerId": player_name, "messageType": msg.get("type")})

	async def send_output(self, player_name: str, message: dict):
		if isinstance(message, dict) and message.get("type") in self.interactiveMessageTypes:
			message = message.copy()

			if "requestId" not in message:
				message["requestId"] = uuid.uuid4().hex

			self.pendingPrompts[player_name] = message.copy()

		messageType = message.get("type") if isinstance(message, dict) else type(message).__name__
		logger.debug("Player output queued", extra={"routerId": player_name, "messageType": messageType})

		queue = self.output_queues.get(player_name)
		if queue:
			await queue.put(message)
		else:
			logger.warning("No output queue found", extra={"routerId": player_name})

	async def get_output(self, player_name: str):
		return await self.output_queues[player_name].get()

	def clear_pending_prompt(self, player_name: str) -> None:
		self.pendingPrompts.pop(player_name, None)

	async def resend_pending_prompt(self, player_name: str) -> None:
		prompt = self.pendingPrompts.get(player_name)
		if prompt is not None:
			await self.send_output(player_name, prompt.copy())

	def forget(self, player_name: str) -> None:
		self.input_queues.pop(player_name, None)
		self.output_queues.pop(player_name, None)
		self.recycleBin.pop(player_name, None)
		self.pendingPrompts.pop(player_name, None)


class ConnectionManager:
	def __init__(self, clock: Clock = SYSTEM_CLOCK, archiveStore: CompressedJsonStore = None):
		self.games: Dict[str, GameSession] = {}
		self._clock = clock
		self._archiveStore = archiveStore

	def _generate_game_id(self) -> str:
		while True:
			gameId = createJoinCode()

			if gameId not in self.games:
				return gameId

	def create_game(self, msg_router, rules: GameRules = MONTSURVENT_RULES, rulesetName: str = None) -> str:
		game_id = self._generate_game_id()
		self.games[game_id] = GameSession(game_id, msg_router, rules, rulesetName, self._clock, self._archiveStore)
		return game_id

	def get_game(self, game_id: str):
		return self.games.get(game_id)

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

			if snapshot.metadata.joinCode == game_id:
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
		self.games[game_id] = session
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

class GameSession:
	def __init__(self, game_id: str, msg_router, rules: GameRules = MONTSURVENT_RULES, rulesetName: str = None, clock: Clock = SYSTEM_CLOCK, archiveStore: CompressedJsonStore = None):
		self.id = game_id
		self._sessionId = createSessionId()
		self._rules = rules
		self._rulesetName = rulesetName if rulesetName is not None else get_matching_preset_name(rules)
		self.players: Dict = {}
		self.started = False
		self.lock = asyncio.Lock()
		self.setupLock = asyncio.Lock()
		self.router = msg_router
		self.order: List = []
		self.game = None
		self.gameTask = None
		self._clock = clock
		self._createdAt = clock.utcNow()
		self._createdMonotonic = clock.monotonic()
		self._startedAt = None
		self._endedAt = None
		self._lastActivityAt = self._createdAt
		self._lastActivityMonotonic = self._createdMonotonic
		self._startedMonotonic = None
		self._eventLog = GameEventLog(self.gameElapsedSeconds)
		self._gameProgress = GameProgressState(GamePhase.DEAL_START, 0)
		self._awaitingResume = False
		self._archiveStore = archiveStore
		self._checkpointLock = asyncio.Lock()
		self._allPlayersDisconnectedMonotonic = None

	@property
	def sessionId(self) -> str:
		return self._sessionId

	@property
	def joinCode(self) -> str:
		return self.id
		
	@property
	def rules(self) -> GameRules:
		return self._rules

	@property
	def rulesetName(self) -> str:
		return self._rulesetName

	@property
	def createdAt(self):
		return self._createdAt

	@property
	def startedAt(self):
		return self._startedAt

	@property
	def endedAt(self):
		return self._endedAt

	@property
	def lastActivityAt(self):
		return self._lastActivityAt

	@property
	def events(self) -> tuple[GameEvent, ...]:
		return self._eventLog.events

	@property
	def gameProgress(self) -> GameProgressState:
		return self._gameProgress

	@property
	def awaitingResume(self) -> bool:
		return self._awaitingResume

	def notePlayerConnected(self) -> None:
		self._allPlayersDisconnectedMonotonic = None

	def notePlayerDisconnected(self) -> None:
		if not self.started:
			return

		if any(playerData.get("active", False) for playerData in self.players.values()):
			return

		if self._allPlayersDisconnectedMonotonic is None:
			self._allPlayersDisconnectedMonotonic = self._clock.monotonic()

	def lobbyHasExpired(self, lifetimeSeconds: float = LOBBY_LIFETIME_SECONDS) -> bool:
		return not self.started and self.lobbyAgeSeconds() >= lifetimeSeconds

	def getSuspensionReason(self, inactivitySeconds: float = GAME_INACTIVITY_SECONDS, disconnectedGraceSeconds: float = ALL_PLAYERS_DISCONNECTED_GRACE_SECONDS) -> str | None:
		if not self.started or self.game is None or self.game.isFinished or self._awaitingResume:
			return None

		if self._allPlayersDisconnectedMonotonic is not None:
			disconnectedSeconds = self._clock.monotonic() - self._allPlayersDisconnectedMonotonic

			if disconnectedSeconds >= disconnectedGraceSeconds:
				return "all-players-disconnected"

		if self.inactivitySeconds() >= inactivitySeconds:
			return "inactive"

		return None

	def setGameProgress(self, progress: GameProgressState) -> None:
		if not isinstance(progress, GameProgressState):
			raise ValueError("Invalid game progress")

		self._gameProgress = progress

	def setGamePhase(self, phase: GamePhase, dealIndex: int = None) -> None:
		if not isinstance(phase, GamePhase):
			raise ValueError("Invalid game phase")

		if dealIndex is None:
			dealIndex = self._gameProgress.dealIndex

		self.setGameProgress(GameProgressState(phase, dealIndex))

	def getPersistentPlayerId(self, player: Player) -> str:
		for playerData in self.players.values():
			if playerData.get("object") is player:
				return playerData["playerId"]

		raise ValueError("Player has no persistent ID in this session")

	def getPlayerByPersistentId(self, playerId: str) -> Player:
		for playerData in self.players.values():
			if playerData["playerId"] == playerId:
				return playerData["object"]

		raise ValueError(f"Unknown persistent player ID: {playerId}")

	@classmethod
	def fromSnapshot(cls, snapshot: SessionSnapshotState, msg_router, clock: Clock = SYSTEM_CLOCK, archiveStore: CompressedJsonStore = None) -> "GameSession":
		if not isinstance(snapshot, SessionSnapshotState):
			raise ValueError("A valid session snapshot is required")

		metadata = snapshot.metadata
		session = cls(metadata.joinCode, msg_router, metadata.rules, metadata.rulesetName, clock, archiveStore)

		session._sessionId = metadata.sessionId
		session._createdAt = metadata.createdAt
		session._startedAt = metadata.startedAt
		session._endedAt = metadata.endedAt
		session._lastActivityAt = metadata.lastActivityAt
		session.started = snapshot.game.isStarted
		session._gameProgress = snapshot.progress

		nowUtc = clock.utcNow()
		nowMonotonic = clock.monotonic()

		session._createdMonotonic = nowMonotonic - max(0.0, (nowUtc - metadata.createdAt).total_seconds())
		session._lastActivityMonotonic = nowMonotonic - max(0.0, (nowUtc - metadata.lastActivityAt).total_seconds())
		session._startedMonotonic = None if metadata.startedAt is None else nowMonotonic - max(0.0, (nowUtc - metadata.startedAt).total_seconds())

		session._eventLog = GameEventLog.from_list([event.to_dict() for event in snapshot.events], session.gameElapsedSeconds)

		runtimeIdsByPersistentId = {}

		for playerState in metadata.players:
			runtimeId = session.getFullPlayerId(metadata.joinCode, playerState.name)
			player = Player(runtimeId, playerState.name, team=playerState.team, color=playerState.color, gameSession=session, router=msg_router)

			session.players[runtimeId] = {
				"name": playerState.name,
				"id": runtimeId,
				"playerId": playerState.playerId,
				"resumeTokenHash": playerState.resumeTokenHash,
				"websocket": None,
				"team": playerState.team,
				"color": playerState.color,
				"object": player,
				"active": False,
				"configured": playerState.configured,
			}

			runtimeIdsByPersistentId[playerState.playerId] = runtimeId
			msg_router.prepareDisconnectedPlayer(runtimeId)

		session.order = [runtimeIdsByPersistentId[playerId] for playerId in snapshot.game.playerOrder]
		snapshot.game.restoreGame(session)

		session._awaitingResume = snapshot.game.isStarted and not snapshot.game.isFinished

		return session

	async def writeCheckpoint(self, category: ArchiveCategory):
		if self._archiveStore is None:
			return None

		if self.game is None:
			raise RuntimeError("Cannot checkpoint a session without a game")

		async with self._checkpointLock:
			payload = self.snapshotState().to_dict()
			return await asyncio.to_thread(self._archiveStore.write, category, self._sessionId, payload)

	async def checkpointActive(self):
		return await self.writeCheckpoint(ArchiveCategory.ACTIVE)

	async def resumed_game_loop(self) -> None:
		try:
			await self.resumeGame()
		except Exception:
			logger.exception("Resumed game loop failed", extra={"gameId": self.id, "sessionId": self._sessionId})

			await self.broadcast(build_message(
				"error",
				"errors.internal_game_error",
				"The game stopped because of an internal server error.",
			))

	async def start_resume_if_ready(self) -> bool:
		async with self.lock:
			if not self._awaitingResume or self.gameTask is not None:
				return False

			if len(self.players) != NUMBER_OF_PLAYERS:
				return False

			if not all(playerData.get("configured", False) and playerData.get("active", False) for playerData in self.players.values()):
				return False

			self.recordActivity()
			await self.activateRestoredArchive()

			self._awaitingResume = False
			self.gameTask = asyncio.create_task(self.resumed_game_loop())
			return True

	async def transitionCheckpoint(self, destination: ArchiveCategory, obsoleteCategories: tuple[ArchiveCategory, ...]):
		if self._archiveStore is None:
			return None

		if self.game is None:
			raise RuntimeError("Cannot archive a session without a game")

		async with self._checkpointLock:
			payload = self.snapshotState().to_dict()

			def persistTransition():
				path = self._archiveStore.write(destination, self._sessionId, payload)

				for category in obsoleteCategories:
					if category is not destination:
						self._archiveStore.delete(category, self._sessionId)

				return path

			return await asyncio.to_thread(persistTransition)

	def completeGameLifecycle(self) -> None:
		if self._endedAt is None:
			self.markEnded()

		if not any(event.eventType is GameEventType.GAME_FINISHED for event in self._eventLog.events):
			self.recordEvent(GameEventType.GAME_FINISHED)

		self.setGamePhase(GamePhase.FINISHED)

	async def resumeGame(self) -> None:
		while True:
			if self.game is None:
				raise RuntimeError("Cannot resume a session without a restored game")

			if self._gameProgress.phase is GamePhase.FINISHED:
				if not self.game.isFinished:
					raise RuntimeError("A session cannot be in the finished phase while its game is unfinished")

				await self.finalizeFinishedGame()
				return

			if self.game.isFinished:
				await self.finalizeFinishedGame()
				return

			await self.resumeCurrentPhase()

	async def resumeCurrentPhase(self) -> None:
		if self.game is None:
			raise RuntimeError("Cannot resume a session without a restored game")

		progress = self._gameProgress

		if progress.phase is GamePhase.FINISHED:
			return

		if progress.phase is GamePhase.DEAL_START:
			cardsPerPlayer = self._rules.deal_card_counts[progress.dealIndex]
			await self.game.runRound(progress.dealIndex + 1, cardsPerPlayer)
			return

		if progress.phase is GamePhase.DEAL_END:
			nextDealIndex = progress.dealIndex + 1

			if nextDealIndex < len(self._rules.deal_card_counts):
				self.setGamePhase(GamePhase.DEAL_START, nextDealIndex)
			else:
				self.setGamePhase(GamePhase.DECK_CYCLE_END)

			await self.checkpointActive()
			return

		if progress.phase is GamePhase.DECK_CYCLE_END:
			self.game.deck.recycleDiscardPile(shuffle=self.game.shouldShuffleRecycledDeck())
			await self.game.nextDealer()
			self.setGamePhase(GamePhase.DEAL_START, 0)
			await self.checkpointActive()
			return

		if progress.phase is GamePhase.CARD_EXCHANGE:
			await self.game.exchangeCards()
			self.setGamePhase(GamePhase.TURN_START)
			await self.checkpointActive()
			return

		if progress.phase is GamePhase.TURN_START:
			if self.game.handsFinished >= self.game.numPlayers:
				self.setGamePhase(GamePhase.DEAL_END)
				await self.checkpointActive()
				return

			await self.game.nextPlayer()
			return

		if progress.phase is GamePhase.TURN_DECISION:
			await self.game.playCurrentTurn()
			return

		if progress.phase is GamePhase.TURN_END:
			await self.game.finishCurrentTurn()
			return

		if progress.phase is GamePhase.SEVEN_SPLIT:
			sevenSplit = progress.sevenSplit
			actingPlayer = self.getPlayerByPersistentId(sevenSplit.actingPlayerId)
			pieceOwner = self.getPlayerByPersistentId(sevenSplit.pieceOwnerId)
			movedPiecePositions = {self.game.board.getPositionById(positionId) for positionId in sevenSplit.movedPositionIds}

			await self.game.playSeven(actingPlayer, pieceOwner, sevenSplit.card.toCard(), sevenSplit.stepsRemaining, movedPiecePositions)
			return

		if progress.phase is GamePhase.SEVEN_HOP:
			sevenHop = progress.sevenHop
			actingPlayer = self.getPlayerByPersistentId(sevenHop.actingPlayerId)
			pieceOwner = self.getPlayerByPersistentId(sevenHop.pieceOwnerId)
			decidingPlayer = self.getPlayerByPersistentId(sevenHop.decidingPlayerId)
			origin = self.game.board.getPositionById(sevenHop.originPositionId)
			target = self.game.board.getPositionById(sevenHop.targetPositionId)
			hopMove = Move("HOP", origin, target, sevenHop.card.toCard(), actingPlayer, pieceOwner)

			await self.game.completeOptionalSevenHop(hopMove, decidingPlayer)
			return

		raise RuntimeError(f"Resuming phase '{progress.phase.value}' is not implemented yet")

	def beginSevenSplit(self, move) -> None:
		self.setGameProgress(GameProgressState(
			phase=GamePhase.SEVEN_SPLIT,
			dealIndex=self._gameProgress.dealIndex,
			sevenSplit=SevenSplitProgressState(
				actingPlayerId=self.getPersistentPlayerId(move.player),
				pieceOwnerId=self.getPersistentPlayerId(move.pieceOwner),
				card=CardState.fromCard(move.card),
				stepsRemaining=7,
			),
		))

	def updateSevenSplit(self, stepsRemaining: int, movedPositionIds: tuple[str, ...] = ()) -> None:
		currentSplit = self._gameProgress.sevenSplit

		if self._gameProgress.phase is not GamePhase.SEVEN_SPLIT or currentSplit is None:
			raise RuntimeError("Cannot update seven-split progress outside a seven split")

		self.setGameProgress(GameProgressState(
			phase=GamePhase.SEVEN_SPLIT,
			dealIndex=self._gameProgress.dealIndex,
			sevenSplit=SevenSplitProgressState(
				actingPlayerId=currentSplit.actingPlayerId,
				pieceOwnerId=currentSplit.pieceOwnerId,
				card=currentSplit.card,
				stepsRemaining=stepsRemaining,
				movedPositionIds=movedPositionIds,
			),
		))

	def beginSevenHop(self, hopMove, decidingPlayer: Player, playedCard=None) -> None:
		card = hopMove.card if playedCard is None else playedCard

		self.setGameProgress(GameProgressState(
			phase=GamePhase.SEVEN_HOP,
			dealIndex=self._gameProgress.dealIndex,
			sevenHop=SevenHopProgressState(
				actingPlayerId=self.getPersistentPlayerId(hopMove.player),
				pieceOwnerId=self.getPersistentPlayerId(hopMove.pieceOwner),
				decidingPlayerId=self.getPersistentPlayerId(decidingPlayer),
				card=CardState.fromCard(card),
				originPositionId=str(hopMove.originSpot),
				targetPositionId=str(hopMove.targetSpot),
			),
		))

	def gameElapsedSeconds(self) -> int:
		if self._startedMonotonic is None:
			return 0

		return max(0, int(self._clock.monotonic() - self._startedMonotonic))

	def recordEvent(self, eventType: GameEventType, playerId: str = None, details: dict = None) -> GameEvent:
		event = self._eventLog.record(eventType, playerId, details)
		self.recordActivity()
		return event

	def lobbyAgeSeconds(self) -> float:
		return self._clock.monotonic() - self._createdMonotonic

	def inactivitySeconds(self) -> float:
		return self._clock.monotonic() - self._lastActivityMonotonic

	def recordActivity(self) -> None:
		self._lastActivityAt = self._clock.utcNow()
		self._lastActivityMonotonic = self._clock.monotonic()

	def markStarted(self) -> None:
		if self._startedAt is not None:
			return

		self._startedAt = self._clock.utcNow()
		self._startedMonotonic = self._clock.monotonic()
		self._lastActivityAt = self._startedAt
		self._lastActivityMonotonic = self._startedMonotonic
		self.started = True

	def markEnded(self) -> None:
		if self._endedAt is not None:
			return

		self._endedAt = self._clock.utcNow()
		self._lastActivityAt = self._endedAt
		self._lastActivityMonotonic = self._clock.monotonic()

	def ruleset_state(self) -> dict:
		return {"preset": self._rulesetName, "values": self._rules.to_dict()}

	def metadataState(self) -> SessionMetadataState:
		return SessionMetadataState.fromGameSession(self)

	def snapshotState(self) -> SessionSnapshotState:
		return SessionSnapshotState.fromGameSession(self)

	async def archiveSuspended(self):
		if self.game is None:
			raise RuntimeError("Cannot suspend a session without a game")

		if self.game.isFinished:
			raise RuntimeError("A finished game cannot be suspended")

		path = await self.transitionCheckpoint(ArchiveCategory.SUSPENDED, (ArchiveCategory.ACTIVE,))

		if path is not None:
			self._awaitingResume = True

		return path

	async def activateRestoredArchive(self):
		return await self.transitionCheckpoint(ArchiveCategory.ACTIVE, (ArchiveCategory.SUSPENDED,))

	async def archiveFinished(self):
		if self.game is None or not self.game.isFinished:
			raise RuntimeError("Cannot archive an unfinished game as finished")

		if self._endedAt is None:
			raise RuntimeError("Cannot archive a finished game without an end timestamp")

		if self._archiveStore is None:
			return None

		async with self._checkpointLock:
			payload = FinishedArchiveState.fromGameSession(self).to_dict()

			def persistFinishedArchive():
				path = self._archiveStore.write(ArchiveCategory.FINISHED, self._sessionId, payload)
				self._archiveStore.delete(ArchiveCategory.ACTIVE, self._sessionId)
				self._archiveStore.delete(ArchiveCategory.SUSPENDED, self._sessionId)
				return path

			path = await asyncio.to_thread(persistFinishedArchive)

		self._awaitingResume = False
		return path

	async def finalizeFinishedGame(self):
		self.completeGameLifecycle()
		return await self.archiveFinished()

	async def closeConnections(self, code: int, reason: str) -> None:
		websockets = []

		for playerData in self.players.values():
			websocket = playerData.get("websocket")

			if playerData.get("active", False) and websocket is not None:
				websockets.append(websocket)

		if websockets:
			await asyncio.gather(*(websocket.close(code=code, reason=reason) for websocket in websockets), return_exceptions=True)

		for runtimeId, playerData in self.players.items():
			playerData["active"] = False
			self.router.forget(runtimeId)

		self._allPlayersDisconnectedMonotonic = None

	async def cancelGameTask(self) -> bool:
		task = self.gameTask

		if task is None or task.done():
			self.gameTask = None
			return False

		if task is asyncio.current_task():
			raise RuntimeError("A game task cannot cancel itself")

		task.cancel()

		with suppress(asyncio.CancelledError):
			await task

		self.gameTask = None
		return True

	async def suspendGame(self) -> None:
		hadRunningTask = await self.cancelGameTask()

		try:
			path = await self.archiveSuspended()

			if path is None:
				raise RuntimeError("Cannot suspend a game without persistent storage")

		except Exception:
			self._awaitingResume = False

			if hadRunningTask and not self.game.isFinished:
				self.gameTask = asyncio.create_task(self.resumed_game_loop())

			raise

	def fullUI(self) -> dict:
		if self.game:
			if self.game.activePlayer:
				active_player_name = self.game.activePlayer.name
			else:
				active_player_name = ""

			return {
				"type": "full-ui-state", 
				"players": [
						{
						"name": self.players[p]["name"], 
						"team": self.players[p]["team"], 
						"color": self.players[p]["color"], 
						"number_of_cards": self.players[p]["object"].hand.size
						}
					for p in self.players
					], 
				"pieces": self.game.board.getAllPiecesOnTheBoard(), 
				"active_player": active_player_name,
				"trackRegionLength": self._rules.track_region_length,
				"enterHouseAtSpot": self._rules.enter_house_at_spot,
				"ruleset": self.ruleset_state()
				}
		else:
			return {
				"type": "full-ui-state", 
				"players": [
						{
						"name": self.players[p]["name"], 
						"team": self.players[p]["team"], 
						"color": self.players[p]["color"], 
						"number_of_cards": self.players[p]["object"].hand.size
						}
					for p in self.players
					], 
				"pieces": [], 
				"active_player": "",
				"trackRegionLength": self._rules.track_region_length,
				"enterHouseAtSpot": self._rules.enter_house_at_spot,
				"ruleset": self.ruleset_state()
				}

	def team_is_full(self, team: str) -> bool:
		return sum([self.players[p]["team"] == team for p in self.players]) >= NUMBER_OF_PLAYERS // NUMBER_OF_TEAMS

	def is_full(self) -> bool:
		return len(self.players) >= NUMBER_OF_PLAYERS

	def available_colors(self) -> list[str]:
		usedColors = {playerData["color"] for playerData in self.players.values() if playerData.get("color")}
		return [color for color in COLORS if color not in usedColors]

	def lobby_state(self) -> dict:
		players = [
				{
				"name": playerData["name"], 
				"team": playerData.get("team", ""), 
				"color": playerData.get("color", ""), 
				"connected": playerData.get("active", False), 
				"configured": playerData.get("configured", False)
				} 
			for playerData in self.players.values()
			]

		teamCounts = {
			team: sum(playerData.get("team") == team for playerData in self.players.values()) for team in ["0", "1"]
			}
		
		return {
			"type": "lobby-state", 
			"gameId": self.id, 
			"started": self.started, 
			"players": players, 
			"availableColors": self.available_colors(), 
			"teamCounts": teamCounts, 
			"teamCapacity": NUMBER_OF_PLAYERS // NUMBER_OF_TEAMS,
			"trackRegionLength": self._rules.track_region_length,
			"enterHouseAtSpot": self._rules.enter_house_at_spot,
			"ruleset": self.ruleset_state()
			}

	async def broadcast_lobby_state(self) -> None:
		await self.broadcast(self.lobby_state())

	def getFullPlayerId(self, game_id : str, player_name : str) -> str:
		return f'{game_id}-{player_name}'

	def set_player_order(self) -> bool:
		if len(self.players) != NUMBER_OF_PLAYERS:
			return False

		playerIds = list(self.players.keys())
		firstPlayerId = playerIds[0]
		firstTeam = self.players[firstPlayerId]["team"]

		teammateIds = [playerId for playerId in playerIds if playerId != firstPlayerId and self.players[playerId]["team"] == firstTeam]
		opponentIds = [playerId for playerId in playerIds if self.players[playerId]["team"] != firstTeam]

		if len(teammateIds) != 1 or len(opponentIds) != 2:
			return False

		self.order = [firstPlayerId, opponentIds[0], teammateIds[0], opponentIds[1]]
		return True

	async def broadcast(self, message: Dict, excluded_player : str = None):
		for player_id in self.players.keys():
			if player_id != excluded_player:
				player = self.players[player_id]['object']
				await player.send_message_to_user(message)

	async def game_loop(self):
		try:
			await self.broadcast(build_message("log", "gameplay.game_starting", "Four players have joined: the game is starting!"))
			self.game = Game(self, [self.players[player_id]["color"] for player_id in self.order], self._rules)
			self.game.setPlayers([self.players[player_id]["object"] for player_id in self.order])
			await self.game.start()
			await self.finalizeFinishedGame()
		except Exception:
			logging.exception("Game loop failed for game %s", self.id)
			await self.broadcast(build_message("error", "errors.internal_game_error", "The game stopped because of an internal server error."))

	async def start_game_if_ready(self) -> bool:
		async with self.lock:
			if self.started or len(self.players) != NUMBER_OF_PLAYERS or len(self.order) != NUMBER_OF_PLAYERS:
				return False

			if not all(player.get("configured", False) for player in self.players.values()):
				return False

			self.markStarted()
			self.recordEvent(GameEventType.GAME_STARTED)

		await self.broadcast_lobby_state()
		self.gameTask = asyncio.create_task(self.game_loop())
		return True

	async def configure_player(self, player_id: str, team: str, color: str) -> bool:
		async with self.setupLock:
			playerData = self.players.get(player_id)

			if playerData is None or self.started:
				return False

			if playerData.get("configured", False):
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.already_confirmed",
					"Your lobby choices have already been confirmed.",
				))
				return False

			if team not in ["0", "1"]:
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.invalid_team",
					"Please choose a valid team.",
				))
				return False

			if color not in COLORS:
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.invalid_color",
					"Please choose a valid colour.",
				))
				return False

			if self.team_is_full(team):
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.team_full",
					f"Team {team} is already full.",
					{"team": team},
				))
				return False

			if color not in self.available_colors():
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.color_taken",
					f"The colour {color} has already been selected.",
					{"color": color},
				))
				return False

			player = playerData["object"]
			player.setTeam(team)
			player.setColor(color)
			playerData["team"] = team
			playerData["color"] = color
			playerData["configured"] = True

			if len(self.players) == NUMBER_OF_PLAYERS and all(data.get("configured", False) for data in self.players.values()):
				if not self.set_player_order():
					raise RuntimeError("Could not determine a valid player order")

		await self.broadcast_lobby_state()
		await self.start_game_if_ready()
		return True

	async def handle_player_message(self, player_id: str, message: dict) -> None:
		messageType = message.get("type")

		if messageType == "configure-player":
			await self.configure_player(player_id, message.get("team", ""), message.get("color", ""))
			return

		if messageType == "debug":
			if message.get("msg") == "simulate_card_exchange_players3and4":
				playerIds = list(self.players.keys())
				player3 = self.players[playerIds[2]]["object"]
				player4 = self.players[playerIds[3]]["object"]

				await self.router.add_input(playerIds[2], {"type": "card_selection", "name": playerIds[2], "value": player3.hand.cards[0].value, "suit": player3.hand.cards[0].suit})
				await self.router.add_input(playerIds[3], {"type": "card_selection", "name": playerIds[3], "value": player4.hand.cards[0].value, "suit": player4.hand.cards[0].suit})

			elif message.get("msg") == "force-play" and self.game is not None and self.game.activePlayer is not None:
				await self.game.activePlayer.forceRandomMove()

			return

		await self.router.add_input(player_id, message)

@app.websocket("/toc/ws/{game_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_name: str):
	await websocket.accept()
	gameSession = manager.get_or_restore_game(game_id, router)

	if gameSession is None:
		await websocket.close(code=NO_GAME_FOUND_CODE)
		return

	player_id = gameSession.getFullPlayerId(game_id, player_name)
	existingPlayer = gameSession.players.get(player_id)

	if existingPlayer is not None and existingPlayer["active"]:
		await websocket.close(code=NO_PLAYER_CONTEXT_FOUND_CODE)
		return

	if existingPlayer is None and gameSession.is_full():
		await websocket.close(code=GAME_ALREADY_FULL_CODE)
		return

	try:
		identityData = await asyncio.wait_for(websocket.receive_text(), timeout=IDENTIFY_TIMEOUT_SECONDS)
	except TimeoutError:
		await websocket.close(code=CONNECTION_IDENTIFICATION_ERROR_CODE, reason="Connection identification timed out")
		return
	except WebSocketDisconnect:
		return

	try:
		identityMessage = json.loads(identityData)
	except json.JSONDecodeError:
		await websocket.close(code=CONNECTION_IDENTIFICATION_ERROR_CODE, reason="Invalid connection identity")
		return

	if not isinstance(identityMessage, dict) or identityMessage.get("type") != "identify":
		await websocket.close(code=CONNECTION_IDENTIFICATION_ERROR_CODE, reason="Invalid connection identity")
		return

	resumeToken = identityMessage.get("resumeToken")

	if resumeToken is not None and not isinstance(resumeToken, str):
		await websocket.close(code=CONNECTION_IDENTIFICATION_ERROR_CODE, reason="Invalid connection identity")
		return

	if existingPlayer is not None and not resumeTokenMatches(resumeToken, existingPlayer["resumeTokenHash"]):
		await websocket.close(code=CONNECTION_IDENTIFICATION_ERROR_CODE, reason="Invalid resume token")
		return

	try:
		if existingPlayer is None:
			persistentPlayerId = createPlayerId()
			resumeToken = createResumeToken()

			router.register(player_id)

			newPlayer = Player(player_id, player_name, "", "", "", gameSession, router)

			gameSession.players[player_id] = {
				"name": player_name,
				"id": player_id,
				"playerId": persistentPlayerId,
				"resumeTokenHash": hashResumeToken(resumeToken),
				"websocket": websocket,
				"team": "",
				"color": "",
				"object": newPlayer,
				"active": True,
				"configured": False,
			}
		else:
			persistentPlayerId = existingPlayer["playerId"]

			router.registerAgain(player_id)
			existingPlayer["websocket"] = websocket
			existingPlayer["active"] = True

		gameSession.notePlayerConnected()

	except (DuplicateNameError, KeyError):
		await websocket.close(code=4003)
		return

	async def input_loop() -> None:
		while True:
			data = await websocket.receive_text()

			try:
				message = json.loads(data)
			except json.JSONDecodeError:
				await router.send_output(player_id, build_message("error", "errors.invalid_json_message", "The server received an invalid JSON message."))
				continue

			if not isinstance(message, dict):
				await router.send_output(player_id, build_message("error", "errors.invalid_message_format", "The server received an invalid message format."))
				continue

			messageType = message.get("type")

			if not isinstance(messageType, str):
				await router.send_output(player_id, build_message("error", "errors.invalid_message_format", "Invalid message format."))
				continue

			if messageType not in CLIENT_MESSAGE_TYPES:
				await router.send_output(player_id, build_message(
					"error",
					"errors.unknown_message_type",
					f"Unknown message type: {messageType}.",
					{"messageType": messageType},
				))
				continue

			await gameSession.handle_player_message(player_id, message)

	async def output_loop() -> None:
		while True:
			message = await router.get_output(player_id)
			await websocket.send_json(message)

	async def setup_connection() -> None:
		if existingPlayer is None:
			await gameSession.broadcast_lobby_state()

		else:
			if gameSession.started:
				await existingPlayer["object"].send_message_to_user(gameSession.lobby_state())
				await existingPlayer["object"].send_message_to_user(gameSession.fullUI())
				await existingPlayer["object"].send_message_to_user(build_message(
					"log",
					"connection.rejoined_self",
					f"You successfully rejoined the game in team {existingPlayer['team']} with colour {existingPlayer['color']}!",
					{"team": existingPlayer["team"], "color": existingPlayer["color"]},
				))
				await existingPlayer["object"].sendHandAgain()
				await router.resend_pending_prompt(player_id)
				await gameSession.broadcast(build_message("log", "connection.player_rejoined", f"{player_name} rejoined the game.", {"player": player_name}), excluded_player=player_id)
			else:
				await gameSession.broadcast_lobby_state()

		startedNewGame = await gameSession.start_game_if_ready()

		if not startedNewGame:
			await gameSession.start_resume_if_ready()
	try:
		await websocket.send_json({
			"type": "ready",
			"protocolVersion": WEBSOCKET_PROTOCOL_VERSION,
			"sessionId": gameSession.sessionId,
			"playerId": persistentPlayerId,
			"resumeToken": resumeToken,
		})

		async with asyncio.TaskGroup() as taskGroup:
			taskGroup.create_task(input_loop())
			taskGroup.create_task(output_loop())
			await setup_connection()

	except* WebSocketDisconnect:
		pass

	except* Exception as errors:
		for error in errors.exceptions:
			logger.error(
				"WebSocket connection failed",
				exc_info=(type(error), error, error.__traceback__),
				extra={
					"sessionId": gameSession.sessionId,
					"joinCode": gameSession.joinCode,
					"routerId": player_id,
					"playerName": player_name,
				},
			)

	finally:
		playerData = gameSession.players.get(player_id)

		if playerData is not None and playerData.get("websocket") is websocket:
			playerData["active"] = False
			gameSession.notePlayerDisconnected()
			router.unregister(player_id)

			if gameSession.started:
				await gameSession.broadcast(build_message("log", "connection.player_disconnected", f"{player_name} disconnected.", {"player": player_name}), excluded_player=player_id)
			else:
				await gameSession.broadcast_lobby_state()


router = PlayerInputRouter()
archiveStore = CompressedJsonStore(GAME_DATA_DIRECTORY)
manager = ConnectionManager(archiveStore=archiveStore)

@app.get("/toc")
async def root():
	return {"message": "Game backend is running."}

@app.get("/toc/api/rule-presets")
async def get_rule_presets():
	return {
		"default": DEFAULT_RULE_PRESET,
		"presets": {name: rules.to_dict() for name, rules in RULE_PRESETS.items()},
		"schema": get_rule_schema(),
		"messageKeys": sorted(MESSAGE_KEYS),
	}

@app.post("/toc/api/create-game")
async def create_game(payload = None):
	if payload is None:
		payload = {}

	if type(payload) is not dict:
		detail = build_message("http-error", "errors.creation_data_object", "Game creation data must be an object.")
		raise HTTPException(status_code=422, detail=detail)

	unknownFields = set(payload) - {"preset", "rules"}

	if unknownFields:
		fields = ", ".join(sorted(unknownFields))
		detail = build_message("http-error", "errors.unknown_creation_fields", f"Unknown game creation fields: {fields}", {"fields": fields})
		raise HTTPException(status_code=422, detail=detail)

	presetName = payload.get("preset", DEFAULT_RULE_PRESET)

	try:
		rules = resolve_ruleset(presetName, payload.get("rules"))
	except ValueError as error:
		detail = build_message("http-error", "errors.invalid_game_configuration", str(error))
		raise HTTPException(status_code=422, detail=detail) from error

	game_id = manager.create_game(router, rules, presetName)
	return {"game_id": game_id, "preset": presetName, "rules": rules.to_dict()}