from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Dict, List

from settings import ALL_PLAYERS_DISCONNECTED_GRACE_SECONDS, GAME_INACTIVITY_SECONDS, LOBBY_LIFETIME_SECONDS
from toc.infrastructure.clock import Clock, SYSTEM_CLOCK
from toc.infrastructure.identity import createSeatId, createSessionId
from toc.infrastructure.messages import build_message
from toc.model.audit import GameEventLog, GameEventType
from toc.model.game import Game
from toc.model.game_mode import DEFAULT_GAME_MODE, GameModeDefinition, getGameModeDefinition
from toc.model.game_phase import GamePhase
from toc.model.move import Move
from toc.model.params import AVAILABLE_COLORS
from toc.model.player import Player
from toc.model.rules import GameRules, MONTSURVENT_RULES, get_matching_preset_name
from toc.persistence.archive_store import ArchiveCategory, CompressedJsonStore
from toc.persistence.finished_state import FinishedArchiveState
from toc.persistence.persistent_state import SessionMetadataState
from toc.persistence.snapshot_state import CardState, GameProgressState, SessionSnapshotState, SevenHopProgressState, SevenSplitProgressState
from toc.session.roster import Participant, PlayerSeat, SessionRoster


logger = logging.getLogger("toc.main")


class GameSession:
	def __init__(self, game_id: str, msg_router, rules: GameRules = MONTSURVENT_RULES, rulesetName: str = None, clock: Clock = SYSTEM_CLOCK, archiveStore: CompressedJsonStore = None, modeDefinition: GameModeDefinition = None, creatorName: str = ""):
		self.id = game_id
		self._sessionId = createSessionId()
		self._rules = rules
		self._rulesetName = rulesetName if rulesetName is not None else get_matching_preset_name(rules)
		self.players: Dict = {}
		self._roster = SessionRoster()
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
		self._creatorName = creatorName

		if modeDefinition is None:
			modeDefinition = getGameModeDefinition(DEFAULT_GAME_MODE)

		if not isinstance(modeDefinition, GameModeDefinition):
			raise ValueError("Invalid game-mode definition")

		self._modeDefinition = modeDefinition

	@property
	def sessionId(self) -> str:
		return self._sessionId

	@property
	def creatorName(self) -> str:
		return self._creatorName

	@property
	def modeDefinition(self) -> GameModeDefinition:
		return self._modeDefinition

	@property
	def dealCardCounts(self) -> tuple[int, ...]:
		return self._modeDefinition.resolveDealCardCounts(self._rules.deal_card_counts)

	@property
	def orderedSeats(self) -> tuple[PlayerSeat, ...]:
		return tuple(self.roster.getSeatById(seatId) for seatId in self.order)
		
	@property
	def roster(self) -> SessionRoster:
		return self._roster

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
		try:
			return self.roster.getSeatForPlayer(player).seatId
		except ValueError:
			pass

		for playerData in self.players.values():
			if playerData.get("object") is player:
				return playerData["playerId"]

		raise ValueError("Player has no persistent ID in this session")

	def getPlayerByPersistentId(self, playerId: str) -> Player:
		try:
			return self.roster.getSeatById(playerId).player
		except ValueError:
			pass

		for playerData in self.players.values():
			if playerData["playerId"] == playerId:
				return playerData["object"]

		raise ValueError(f"Unknown persistent player ID: {playerId}")

	async def sendHandsAgain(self, playerData: dict) -> None:
		players = playerData.get("objects", [])

		if not players and playerData.get("object") is not None:
			players = [playerData["object"]]

		for player in players:
			await player.sendHandAgain()

	@classmethod
	def fromSnapshot(cls, snapshot: SessionSnapshotState, msg_router, clock: Clock = SYSTEM_CLOCK, archiveStore: CompressedJsonStore = None) -> "GameSession":
		if not isinstance(snapshot, SessionSnapshotState):
			raise ValueError("A valid session snapshot is required")

		metadata = snapshot.metadata
		session = cls(metadata.joinCode, msg_router, metadata.rules, metadata.rulesetName, clock, archiveStore, metadata.modeDefinition)

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

		participantsById = {}

		for participantState in metadata.participants:
			runtimeId = session.getFullPlayerId(metadata.joinCode, participantState.name)
			participant = Participant(
				participantId=participantState.participantId,
				routerId=runtimeId,
				name=participantState.name,
				resumeTokenHash=participantState.resumeTokenHash,
				websocket=None,
				active=False,
				configured=participantState.configured,
			)

			session.roster.addParticipant(participant)
			participantsById[participant.participantId] = participant
			msg_router.prepareDisconnectedPlayer(runtimeId)

			session.players[runtimeId] = {
				"name": participant.name,
				"id": runtimeId,
				"playerId": participant.participantId,
				"participantId": participant.participantId,
				"resumeTokenHash": participant.resumeTokenHash,
				"websocket": None,
				"team": "",
				"color": "",
				"colors": [],
				"object": None,
				"objects": [],
				"participant": participant,
				"seat": None,
				"seats": [],
				"active": False,
				"configured": participant.configured,
			}

		for seatState in metadata.seats:
			try:
				participant = participantsById[seatState.participantId]
			except KeyError as error:
				raise ValueError("Restored seat references an unknown participant") from error

			runtimeId = participant.routerId

			player = Player(
				identifier=seatState.seatId,
				name=participant.name,
				team=seatState.team,
				color=seatState.color,
				gameSession=session,
				router=msg_router,
				routerId=runtimeId,
			)

			seat = PlayerSeat(
				seatId=seatState.seatId,
				participantId=participant.participantId,
				team=seatState.team,
				color=seatState.color,
				player=player,
			)

			session.roster.addSeat(seat)

			playerData = session.players[runtimeId]

			if playerData["team"] and playerData["team"] != seat.team:
				raise ValueError("Restored participant controls seats from different teams")

			playerData["objects"].append(player)
			playerData["seats"].append(seat)
			playerData["colors"].append(seat.color)

			if playerData["object"] is None:
				playerData["team"] = seat.team
				playerData["color"] = seat.color
				playerData["object"] = player
				playerData["seat"] = seat

		session.order = list(snapshot.game.playerOrder)
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
		self.recordActivity()
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

			if len(self.players) != self._modeDefinition.participantCount:
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

	def getGameFinishedAuditDetails(self) -> dict:
		winningPlayers = self.game.getWinningTeam() if self.game is not None else None

		if winningPlayers is None:
			return {
				"winningTeam": None,
				"winningSeatIds": [],
				"winningParticipantIds": [],
				"winnerNames": [],
			}

		winningSeatIds = [self.getPersistentPlayerId(player) for player in winningPlayers]
		winningParticipantIds = list(dict.fromkeys(self.roster.getParticipantForPlayer(player).participantId for player in winningPlayers))
		winnerNames = [self.roster.getParticipantById(participantId).name for participantId in winningParticipantIds]

		return {
			"winningTeam": winningPlayers[0].team,
			"winningSeatIds": winningSeatIds,
			"winningParticipantIds": winningParticipantIds,
			"winnerNames": winnerNames,
		}

	def completeGameLifecycle(self) -> None:
		if self._endedAt is None:
			self.markEnded()

		if not any(event.eventType is GameEventType.GAME_FINISHED for event in self._eventLog.events):
			self.recordEvent(GameEventType.GAME_FINISHED, details=self.getGameFinishedAuditDetails())

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
			cardsPerPlayer = self.game.dealCardCounts[progress.dealIndex]
			await self.game.runRound(progress.dealIndex + 1, cardsPerPlayer)
			return

		if progress.phase is GamePhase.DEAL_END:
			nextDealIndex = progress.dealIndex + 1

			if nextDealIndex < len(self.game.dealCardCounts):
				self.setGamePhase(GamePhase.DEAL_START, nextDealIndex)
			else:
				self.setGamePhase(GamePhase.DECK_CYCLE_END)

			await self.checkpointActive()
			return

		if progress.phase is GamePhase.DECK_CYCLE_END:
			await self.game.recycleDeck()
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

	def recordPlayerEvent(self, eventType: GameEventType, player: Player, details: dict = None) -> GameEvent:
		return self.recordEvent(eventType, self.getPersistentPlayerId(player), details)

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
		values = self._rules.to_dict()
		seatsPerTeam = self._modeDefinition.seatCount // self._modeDefinition.teamCount

		values["card_exchange"] = self._rules.card_exchange and seatsPerTeam == 2
		values["deal_card_counts"] = list(self.dealCardCounts)

		return {"preset": self._rulesetName, "values": values}

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
		if len(self.order) == self.roster.seatCount:
			seats = self.orderedSeats
		else:
			seats = self.roster.seats

		activePlayer = self.game.activePlayer if self.game is not None else None

		lastPlayedCard = self.game.lastPlayedCard if self.game is not None else None

		players = [
			{
				"name": seat.player.name,
				"playerId": seat.player.name,
				"seatId": seat.seatId,
				"participantId": seat.participantId,
				"team": seat.team,
				"color": seat.color,
				"number_of_cards": seat.player.hand.size,
			}
			for seat in seats
		]

		return {
			"type": "full-ui-state",
			"players": players,
			"pieces": self.game.board.getAllPiecesOnTheBoard() if self.game is not None else [],
			"active_player": activePlayer.name if activePlayer is not None else "",
			"activeSeatId": activePlayer.identifier if activePlayer is not None else None,
			"trackRegionLength": self._rules.track_region_length,
			"trackRegionCount": self._modeDefinition.seatCount,
			"enterHouseAtSpot": self._rules.enter_house_at_spot,
			"ruleset": self.ruleset_state(),
			"lastPlayedCard": {
				"value": lastPlayedCard.value,
				"suit": lastPlayedCard.suit,
			} if lastPlayedCard is not None else None,
		}

	def team_is_full(self, team: str) -> bool:
		return sum(playerData["team"] == team for playerData in self.players.values()) >= self._modeDefinition.participantsPerTeam

	def is_full(self) -> bool:
		return len(self.players) >= self._modeDefinition.participantCount

	def available_colors(self) -> list[str]:
		usedColors = {seat.color for seat in self.roster.seats}
		return [color for color in AVAILABLE_COLORS if color not in usedColors]

	def lobby_state(self) -> dict:
		players = []

		for playerData in self.players.values():
			seats = playerData.get("seats", [])
			colors = [seat.color for seat in seats]

			players.append({
				"name": playerData["name"],
				"team": playerData.get("team", ""),
				"color": colors[0] if colors else "",
				"colors": colors,
				"seats": [{"seatId": seat.seatId, "color": seat.color} for seat in seats],
				"connected": playerData.get("active", False),
				"configured": playerData.get("configured", False),
			})

		teamCounts = {
			team: sum(playerData.get("team") == team for playerData in self.players.values()) for team in self._modeDefinition.teamIds
			}
		
		return {
			"type": "lobby-state", 
			"gameId": self.id, 
			"started": self.started, 
			"players": players, 
			"availableColors": self.available_colors(), 
			"teamCounts": teamCounts, 
			"teamCapacity": self._modeDefinition.participantsPerTeam,
			"participantCapacity": self._modeDefinition.participantCount,
			"seatCapacity": self._modeDefinition.seatCount,
			"seatOrder": list(self.order),
			"gameMode": {
				"name": self._modeDefinition.mode.value,
				"layout": self._modeDefinition.layout.value if self._modeDefinition.layout is not None else None,
			},
			"trackRegionLength": self._rules.track_region_length,
			"trackRegionCount": self._modeDefinition.seatCount,
			"enterHouseAtSpot": self._rules.enter_house_at_spot,
			"ruleset": self.ruleset_state(),
			"seatsPerParticipant": self._modeDefinition.seatsPerParticipant,
			"creatorName": self._creatorName,
			}

	async def broadcast_lobby_state(self) -> None:
		await self.broadcast(self.lobby_state())

	def getFullPlayerId(self, game_id : str, player_name : str) -> str:
		return f'{game_id}-{player_name}'

	def set_player_order(self) -> bool:
		try:
			self.order = list(self.roster.determineSeatOrder(self._modeDefinition))
		except ValueError:
			self.order = []
			return False

		return True

	async def broadcast(self, message: Dict, excluded_player : str = None):
		for player_id in self.players.keys():
			if player_id != excluded_player:
				player = self.players[player_id]['object']
				await player.send_message_to_user(message)

	async def game_loop(self):
		try:
			await self.broadcast(build_message("log", "gameplay.game_starting", "Everyone has joined: the game is starting!"))
			orderedSeats = self.orderedSeats
			self.game = Game(self, [seat.color for seat in orderedSeats], self._rules, self.dealCardCounts, self._modeDefinition.jokerCount)
			self.game.setPlayers([seat.player for seat in orderedSeats])
			await self.game.start()
			await self.finalizeFinishedGame()
		except Exception:
			logging.exception("Game loop failed for game %s", self.id)
			await self.broadcast(build_message("error", "errors.internal_game_error", "The game stopped because of an internal server error."))

	async def start_game_if_ready(self) -> bool:
		async with self.lock:
			if self.started or len(self.players) != self._modeDefinition.participantCount or len(self.order) != self._modeDefinition.seatCount:
				return False

			if not all(player.get("configured", False) for player in self.players.values()):
				return False

			self.markStarted()
			self.recordEvent(GameEventType.GAME_STARTED)

		await self.broadcast_lobby_state()
		self.gameTask = asyncio.create_task(self.game_loop())
		return True

	async def configure_player(self, player_id: str, team: str, colors) -> bool:
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

			if team not in self._modeDefinition.teamIds:
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.invalid_team",
					"Please choose a valid team.",
				))
				return False

			if type(colors) is str:
				colors = [colors]
			elif type(colors) is list:
				colors = colors.copy()

			expectedColorCount = self._modeDefinition.seatsPerParticipant

			if type(colors) is not list or len(colors) != expectedColorCount:
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.invalid_color_count",
					f"Please select {expectedColorCount} colours.",
					{"count": expectedColorCount},
				))
				return False

			if len(set(colors)) != len(colors) or any(color not in AVAILABLE_COLORS for color in colors):
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.invalid_color",
					"Please choose valid and distinct colours.",
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

			availableColors = set(self.available_colors())
			takenColor = next((color for color in colors if color not in availableColors), None)

			if takenColor is not None:
				await playerData["object"].send_message_to_user(build_message(
					"lobby-error",
					"lobby.errors.color_taken",
					f"The colour {takenColor} has already been selected.",
					{"color": takenColor},
				))
				return False

			participant = playerData.get("participant")

			if participant is None:
				raise RuntimeError("Configured player has no registered participant")

			players = []
			seats = []

			for colorIndex, color in enumerate(colors):
				if colorIndex == 0:
					seatId = participant.participantId
					player = playerData["object"]
					player.setTeam(team)
					player.setColor(color)
				else:
					seatId = createSeatId()
					player = Player(
						identifier=seatId,
						name=participant.name,
						team=team,
						color=color,
						gameSession=self,
						router=self.router,
						routerId=participant.routerId,
					)

				seat = PlayerSeat(
					seatId=seatId,
					participantId=participant.participantId,
					team=team,
					color=color,
					player=player,
				)

				players.append(player)
				seats.append(seat)

			for seat in seats:
				self.roster.addSeat(seat)

			playerData["team"] = team
			playerData["color"] = colors[0]
			playerData["colors"] = colors
			playerData["object"] = players[0]
			playerData["objects"] = players
			playerData["seat"] = seats[0]
			playerData["seats"] = seats
			playerData["configured"] = True
			participant.configured = True

			if len(self.players) == self._modeDefinition.participantCount and all(data.get("configured", False) for data in self.players.values()):
				if not self.set_player_order():
					raise RuntimeError("Could not determine a valid player order")

		await self.broadcast_lobby_state()
		await self.start_game_if_ready()
		return True

	async def handle_player_message(self, player_id: str, message: dict) -> None:
		messageType = message.get("type")

		if messageType == "configure-player":
			colors = message.get("colors")

			if colors is None:
				colors = message.get("color", "")

			await self.configure_player(player_id, message.get("team", ""), colors)
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
