from __future__ import annotations

import asyncio
import logging
import uuid

logger = logging.getLogger("toc.main")

INPUT_QUEUE_MAX_SIZE = 1

Message = dict[str, object]
MessageQueue = asyncio.Queue[Message]


class DuplicateNameError(Exception):
	pass


class PlayerInputRouter:
	def __init__(self) -> None:
		self.inputQueues: dict[str, MessageQueue] = {}
		self.outputQueues: dict[str, MessageQueue] = {}
		self.recycleBin: dict[str, dict[str, MessageQueue]] = {}
		self.pendingPrompts: dict[str, Message] = {}
		self.interactiveMessageTypes: set[str] = {"query-card", "query-card-exchange", "query-origin", "query-target", "query-seven-hop"}

	def register(self, playerName: str) -> None:
		if playerName in self.inputQueues:
			logger.info("Attempted to re-registered a user with same name", extra={"routerId": playerName})
			raise DuplicateNameError
		else:
			logger.info("Player registered with router", extra={"routerId": playerName})
			self.inputQueues[playerName] = asyncio.Queue(maxsize=INPUT_QUEUE_MAX_SIZE)
			self.outputQueues[playerName] = asyncio.Queue()

	def registerAgain(self, playerName: str) -> None:
		logger.info("Player re-registered with router", extra={"routerId": playerName})
		queues = self.recycleBin.pop(playerName)
		self.inputQueues[playerName] = queues["in"]
		self.outputQueues[playerName] = queues["out"]

	def unregister(self, playerName: str) -> None:
		if playerName not in self.inputQueues:
			return

		logger.info("Player unregistered from router", extra={"routerId": playerName})
		self.recycleBin[playerName] = {
			"in": self.inputQueues.pop(playerName),
			"out": self.outputQueues.pop(playerName),
		}

	def prepareDisconnectedPlayer(self, playerName: str) -> None:
		self.inputQueues.pop(playerName, None)
		self.outputQueues.pop(playerName, None)
		self.recycleBin.pop(playerName, None)
		self.pendingPrompts.pop(playerName, None)

		self.recycleBin[playerName] = {
			"in": asyncio.Queue(maxsize=INPUT_QUEUE_MAX_SIZE),
			"out": asyncio.Queue(),
		}

	async def addInput(self, playerName: str, message: Message) -> bool:
		messageType = message.get("type") if isinstance(message, dict) else type(message).__name__
		queue = self.inputQueues.get(playerName)

		if queue is None:
			logger.warning("No input queue found", extra={"routerId": playerName})
			return False

		pendingPrompt = self.pendingPrompts.get(playerName)

		if pendingPrompt is None:
			logger.info("Ignored unsolicited player input", extra={"routerId": playerName, "messageType": messageType})
			return False

		requestId = message.get("requestId") if isinstance(message, dict) else None

		if requestId != pendingPrompt.get("requestId"):
			logger.info("Ignored stale player input", extra={"routerId": playerName, "messageType": messageType})
			return False

		if queue.full():
			queuedMessage = queue.get_nowait()
			queuedRequestId = queuedMessage.get("requestId") if isinstance(queuedMessage, dict) else None

			if queuedRequestId == requestId:
				queue.put_nowait(queuedMessage)
				logger.info("Ignored duplicate player input", extra={"routerId": playerName, "messageType": messageType})
				return False

			logger.info("Discarded queued input for an obsolete prompt", extra={"routerId": playerName, "messageType": messageType})

		queue.put_nowait(message)
		logger.debug("Player input queued", extra={"routerId": playerName, "messageType": messageType})
		return True

	async def waitForInput(self, playerName: str) -> Message:
		while True:
			message = await self.inputQueues[playerName].get()
			pendingPrompt = self.pendingPrompts.get(playerName)
			requestId = message.get("requestId") if isinstance(message, dict) else None

			if pendingPrompt is not None and requestId == pendingPrompt.get("requestId"):
				return message

			messageType = message.get("type") if isinstance(message, dict) else type(message).__name__
			logger.info("Ignored stale queued player input", extra={"routerId": playerName, "messageType": messageType})

	async def sendOutput(self, playerName: str, message: Message) -> None:
		if isinstance(message, dict) and message.get("type") in self.interactiveMessageTypes:
			message = message.copy()

			if "requestId" not in message:
				message["requestId"] = uuid.uuid4().hex

			self.pendingPrompts[playerName] = message.copy()

		messageType = message.get("type") if isinstance(message, dict) else type(message).__name__
		logger.debug("Player output queued", extra={"routerId": playerName, "messageType": messageType})

		queue = self.outputQueues.get(playerName)
		if queue is not None:
			await queue.put(message)
		else:
			logger.warning("No output queue found", extra={"routerId": playerName})

	async def getOutput(self, playerName: str) -> Message:
		return await self.outputQueues[playerName].get()

	def clearPendingPrompt(self, playerName: str) -> None:
		self.pendingPrompts.pop(playerName, None)

	async def resendPendingPrompt(self, playerName: str) -> None:
		prompt = self.pendingPrompts.get(playerName)
		if prompt is not None:
			await self.sendOutput(playerName, prompt.copy())

	def forget(self, playerName: str) -> None:
		self.inputQueues.pop(playerName, None)
		self.outputQueues.pop(playerName, None)
		self.recycleBin.pop(playerName, None)
		self.pendingPrompts.pop(playerName, None)
