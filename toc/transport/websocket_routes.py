from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from settings import CLIENT_MESSAGE_TYPES, CONNECTION_IDENTIFICATION_ERROR_CODE, GAME_ALREADY_FULL_CODE, NO_GAME_FOUND_CODE, NO_PLAYER_CONTEXT_FOUND_CODE
from toc.infrastructure.identity import createPlayerId, createResumeToken, hashResumeToken, normalizeJoinCode, resumeTokenMatches
from toc.infrastructure.messages import build_message
from toc.infrastructure.versions import WEBSOCKET_PROTOCOL_VERSION
from toc.model.params import IDENTIFY_TIMEOUT_SECONDS
from toc.model.player import Player
from toc.runtime import manager, router
from toc.session.input_router import DuplicateNameError
from toc.session.roster import Participant


logger = logging.getLogger("toc.main")
websocketRouter = APIRouter()


@websocketRouter.websocket("/toc/ws/{game_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_name: str):
	await websocket.accept()
	
	try:
		game_id = normalizeJoinCode(game_id)
	except ValueError:
		await websocket.close(code=4001)
		return

	gameSession = manager.get_or_restore_game(game_id, router)

	if gameSession is None:
		await websocket.close(code=NO_GAME_FOUND_CODE)
		return

	player_id = gameSession.getFullPlayerId(gameSession.joinCode, player_name)
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
			resumeTokenHash = hashResumeToken(resumeToken)

			router.register(player_id)

			newPlayer = Player(identifier=persistentPlayerId, name=player_name, team="", color="", position="", gameSession=gameSession, router=router, routerId=player_id)

			participant = Participant(
				participantId=persistentPlayerId,
				routerId=player_id,
				name=player_name,
				resumeTokenHash=resumeTokenHash,
				websocket=websocket,
				active=True,
				configured=False,
			)

			gameSession.roster.addParticipant(participant)

			gameSession.players[player_id] = {
				"name": player_name,
				"id": player_id,
				"playerId": persistentPlayerId,
				"resumeTokenHash": resumeTokenHash,
				"websocket": websocket,
				"team": "",
				"color": "",
				"object": newPlayer,
				"participant": participant,
				"participantId": persistentPlayerId,
				"active": True,
				"configured": False,
				"seat": None,
				"colors": [],
				"objects": [],
				"seats": [],
			}
		else:
			persistentPlayerId = existingPlayer["playerId"]

			router.registerAgain(player_id)
			existingPlayer["websocket"] = websocket
			existingPlayer["active"] = True
			participant = existingPlayer["participant"]
			participant.websocket = websocket
			participant.active = True

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
				await gameSession.sendHandsAgain(existingPlayer)
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
			playerData["websocket"] = None
			playerData["active"] = False

			participant = playerData.get("participant")

			if participant is not None:
				participant.websocket = None
				participant.active = False

			gameSession.notePlayerDisconnected()
			router.unregister(player_id)

			if gameSession.started:
				await gameSession.broadcast(build_message("log", "connection.player_disconnected", f"{player_name} disconnected.", {"player": player_name}), excluded_player=player_id)
			else:
				await gameSession.broadcast_lobby_state()
