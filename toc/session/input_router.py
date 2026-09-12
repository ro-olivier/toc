from __future__ import annotations

import asyncio
import logging
import uuid


logger = logging.getLogger("toc.main")


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
