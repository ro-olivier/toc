from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from settings import CLIENT_MESSAGE_TYPES, CONNECTION_IDENTIFICATION_ERROR_CODE, GAME_ALREADY_FULL_CODE, NO_GAME_FOUND_CODE, NO_PLAYER_CONTEXT_FOUND_CODE, MAX_PLAYER_NAME_LENGTH, INVALID_PLAYER_NAME_CODE
from toc.infrastructure.identity import createPlayerId, createResumeToken, hashResumeToken, normalizeJoinCode, resumeTokenMatches
from toc.infrastructure.messages import buildMessage
from toc.infrastructure.versions import WEBSOCKET_PROTOCOL_VERSION
from toc.model.params import IDENTIFY_TIMEOUT_SECONDS
from toc.model.player import Player
from toc.runtime import manager, router
from toc.session.input_router import DuplicateNameError
from toc.session.roster import Participant
from toc.session.session_participant import SessionParticipant


logger = logging.getLogger("toc.main")
websocketRouter = APIRouter()


@websocketRouter.websocket("/toc/ws/{gameId}/{playerName}")
async def websocket_endpoint(websocket: WebSocket, gameId: str, playerName: str) -> None:
	await websocket.accept()

	playerName = playerName.strip()

	if not playerName or len(playerName) > MAX_PLAYER_NAME_LENGTH:
		await websocket.close(code=INVALID_PLAYER_NAME_CODE, reason="Invalid player name")
		return
	
	try:
		gameId = normalizeJoinCode(gameId)
	except ValueError:
		await websocket.close(code=4001)
		return

	gameSession = manager.getOrRestoreGame(gameId, router)

	if gameSession is None:
		await websocket.close(code=NO_GAME_FOUND_CODE)
		return

	routerId = gameSession.buildRouterId(gameSession.joinCode, playerName)
	existingParticipant = gameSession.participants.get(routerId)

	if existingParticipant is not None and existingParticipant.active:
		await websocket.close(code=NO_PLAYER_CONTEXT_FOUND_CODE)
		return

	if existingParticipant is None and gameSession.isFull():
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

	if existingParticipant is not None and not resumeTokenMatches(resumeToken, existingParticipant.resumeTokenHash):
		await websocket.close(code=CONNECTION_IDENTIFICATION_ERROR_CODE, reason="Invalid resume token")
		return

	try:
		if existingParticipant is None:
			participantId = createPlayerId()
			resumeToken = createResumeToken()
			resumeTokenHash = hashResumeToken(resumeToken)

			router.register(routerId)

			newPlayer = Player(identifier=participantId, name=playerName, team="", color="", position="", gameSession=gameSession, router=router, routerId=routerId)

			participant = Participant(
				participantId=participantId,
				routerId=routerId,
				name=playerName,
				resumeTokenHash=resumeTokenHash,
				websocket=websocket,
				active=True,
				configured=False,
			)

			gameSession.roster.addParticipant(participant)

			gameSession.participants[routerId] = SessionParticipant(participant, newPlayer)
		else:
			participantId = existingParticipant.participantId

			router.registerAgain(routerId)
			existingParticipant.websocket = websocket
			existingParticipant.active = True

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
				await router.sendOutput(routerId, buildMessage("error", "errors.invalid_json_message", "The server received an invalid JSON message."))
				continue

			if not isinstance(message, dict):
				await router.sendOutput(routerId, buildMessage("error", "errors.invalid_message_format", "The server received an invalid message format."))
				continue

			messageType = message.get("type")

			if not isinstance(messageType, str):
				await router.sendOutput(routerId, buildMessage("error", "errors.invalid_message_format", "Invalid message format."))
				continue

			if messageType not in CLIENT_MESSAGE_TYPES:
				await router.sendOutput(routerId, buildMessage(
					"error",
					"errors.unknown_message_type",
					f"Unknown message type: {messageType}.",
					{"messageType": messageType},
				))
				continue

			await gameSession.handlePlayerMessage(routerId, message)

	async def output_loop() -> None:
		while True:
			message = await router.getOutput(routerId)
			await websocket.send_json(message)

	async def setup_connection() -> None:
		if existingParticipant is None:
			await gameSession.broadcastLobbyState()

		else:
			if gameSession.started:
				await existingParticipant.primaryPlayer.send_message_to_user(gameSession.lobbyState())
				await existingParticipant.primaryPlayer.send_message_to_user(gameSession.fullUI())
				await existingParticipant.primaryPlayer.send_message_to_user(buildMessage(
					"log",
					"connection.rejoined_self",
					f"You successfully rejoined the game in team {existingParticipant.team} with colour {existingParticipant.color}!",
					{"team": existingParticipant.team, "color": existingParticipant.color},
				))
				await gameSession.sendHandsAgain(existingParticipant)
				await router.resendPendingPrompt(routerId)
				await gameSession.broadcast(buildMessage("log", "connection.player_rejoined", f"{playerName} rejoined the game.", {"player": playerName}), excludedRouterId=routerId)
			else:
				await gameSession.broadcastLobbyState()

		startedNewGame = await gameSession.startGameIfReady()

		if not startedNewGame:
			await gameSession.startResumeIfReady()
	try:
		await websocket.send_json({
			"type": "ready",
			"protocolVersion": WEBSOCKET_PROTOCOL_VERSION,
			"sessionId": gameSession.sessionId,
			"playerId": participantId,
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
					"routerId": routerId,
					"playerName": playerName,
				},
			)

	finally:
		sessionParticipant = gameSession.participants.get(routerId)

		if sessionParticipant is not None and sessionParticipant.websocket is websocket:
			sessionParticipant.websocket = None
			sessionParticipant.active = False

			gameSession.notePlayerDisconnected()
			router.unregister(routerId)

			if gameSession.started:
				await gameSession.broadcast(buildMessage("log", "connection.player_disconnected", f"{playerName} disconnected.", {"player": playerName}), excludedRouterId=routerId)
			else:
				await gameSession.broadcastLobbyState()
