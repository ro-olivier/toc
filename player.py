from __future__ import annotations

import random

from cards import Card
from hand import Hand
from messages import build_message
import logging

logger = logging.getLogger("toc.player")

import json


class Player:
	def __init__(self, identifier : str, name : str, team : str = None, color : str = None, position : str = None, gameSession = None, router = None):
		self._id = identifier
		self._name = name
		self._team = team
		self._color = color
		self._position = position
		self._hand = Hand(player = self)
		self._active = False
		self._isDealer = False
		self._piecesOnTheBoard = 0
		self._gameSession = gameSession
		self._router = router
		self.board = None

	def __str__(self) -> str:
		return f'{self._name} in team {self._team} playing {self._color}'

	async def send_message_to_user(self, message: str) -> None:
		await self._router.send_output(self._id, message)

	async def get_input_from_prompt(self, messageKey: str, fallback: str, parameters: dict = None) -> str:
		await self.send_message_to_user(build_message("query", messageKey, fallback, parameters))
		logger.info("Waiting for input from player", extra={"player_name": self._name})
		return await self._router.wait_for_input(self._id)
		
	@property
	def name(self) -> str:
		return self._name

	@property
	def team(self) -> str:
		return self._team

	def setTeam(self, team : str) -> None:
		self._team = team

	@property
	def color(self) -> str:
		return self._color

	def setColor(self, color : str) -> None:
		self._color = color

	@property
	def position(self) -> str:
		return self._position

	def setPosition(self, position : str) -> None:
		self._position = position

	@property
	def hand(self) -> Hand:
		return self._hand

	@property
	def piecesOnTheBoard(self) -> int:
		return self._piecesOnTheBoard

	def addAPieceOnTheBoard(self) -> None:
		self._piecesOnTheBoard += 1

	def removeAPieceFromTheBoard(self) -> None:
		self._piecesOnTheBoard -= 1

	def setBoard(self, board) -> None:
		self._board = board

	async def setHand(self, hand : Hand) -> None:
		self._hand = hand
		await self.send_message_to_user({"type": "draw", "playerId": self._name, "cards": [c.json for c in self._hand.cards]})
		await self.send_message_to_user({"type": "reveal", "playerId": self._name, "cards": [c.json for c in self._hand.cards]})

	async def sendHandAgain(self) -> None:
		await self.send_message_to_user({"type": "reveal", "playerId": self._name, "cards": [c.json for c in self._hand.cards]})

	@property
	def isDealer(self) -> bool:
		return self._isDealer

	def setDealer(self, isDealer: bool = True) -> None:
		self._isDealer = isDealer

	async def foldHand(self) -> None:
		 self._hand.fold()

	async def getCardChoiceFromPlayer(self, messageKey: str = "prompts.choose_card", fallback: str = "What card do you want to play?") -> Card:
		await self.send_message_to_user(build_message("query-card", messageKey, fallback))
		cardChoice = await self.get_input_from_prompt(messageKey, fallback)

		while not cardChoice or (not 'type' in cardChoice.keys()) or (cardChoice['type'] != 'card_selection') or (not Card(cardChoice['suit'], cardChoice['value']) in self._hand.cards):
			cardChoice = await self.get_input_from_prompt(messageKey, fallback)

		chosenCard = Card(cardChoice['suit'], cardChoice['value'])
		self._router.clear_pending_prompt(self._id)
		logger.debug('Card chosen by player', extra={"chosenCard": str(chosenCard), "playerName": self._name})
		return chosenCard

	async def getMoveChoiceFromPlayer(self, options : list[Move]) -> Move:

		for move in options:
			move.updateDescription()

		cardChoice = await self.getCardChoiceFromPlayer()
		logger.debug('selected card', extra={"chosenCard": str(cardChoice)})
		moveChoice = None
		## TODO: investigate infinite loop when a player played a not-speacil card with only a 7 remaining, which seem to have triggered an infinite loop (which I didn't screenshot unfortunately...)
		while not moveChoice:
			possibleMoves = [move for move in options if move.card == cardChoice]
			logger.debug('Possible moves with this card:', extra={"possibleMoves": [f'{str(m)} ---- origin: {m.originSpot} {id(m.originSpot)}' for m in possibleMoves]})
			if len(possibleMoves) == 0:
				await self.send_message_to_user(build_message("reject-card-selection", "prompts.card_unplayable", "You cannot play that card right now!"))
				cardChoice = await self.getCardChoiceFromPlayer()
			elif len(possibleMoves) == 1:
				moveChoice = possibleMoves[0]
			else:

				possibleOrigins = list(set([move.originSpot for move in possibleMoves if move.card == cardChoice]))
				if len(possibleOrigins) == 1: # There could be one single origin, but several targets (for example an A being played with only one piece out and no more pieces to take out), and so here we may skip asking the player to choose the origin
					origin = possibleOrigins[0]
				else:
					origin = await self.getOriginChoiceFromPlayer(possibleOrigins, canCancel=True)
					if origin is None:
						cardChoice = await self.getCardChoiceFromPlayer()
						continue

				logger.debug('originSpot selected', extra={"originSpot": str(origin)})

				possibleTargets = list(set([move.targetSpot for move in possibleMoves if move.originSpot == origin and move.card == cardChoice]))

				if len(possibleTargets) == 1: # There could be only one possible target for several moves from different origins (for example you have two pieces seperated by 4 spots and you have only a 4 and an 8 to play), and se here we may skip asking the player to choose the target
					target = possibleTargets[0]
				else:
					target = await self.getTargetChoiceFromPlayer(possibleTargets, canCancel=True)
					if target is None:
						cardChoice = await self.getCardChoiceFromPlayer()
						continue

				logger.debug('targetSpot selected', extra={"targetSpot": str(target)})
				result = [move for move in possibleMoves if move.originSpot == origin and move.card == cardChoice and move.targetSpot == target]
				#TODO should we test here if there is only one resulting move? I don't see why there should not be but if not, we're screwed
				moveChoice = result[0]
			
		return moveChoice

	async def getOriginChoiceFromPlayer(self, possibleOrigins, canCancel: bool = False) -> Spot:
		messageKey = "prompts.choose_origin"
		fallback = "What piece do you want to play this card on?"

		await self.send_message_to_user(build_message("query-origin", messageKey, fallback, originOptions=[str(origin) for origin in possibleOrigins], canCancel=canCancel))

		originsById = {str(origin): origin for origin in possibleOrigins}
		while True:
			spotChoice = await self.get_input_from_prompt(messageKey, fallback)
			if canCancel and isinstance(spotChoice, dict) and spotChoice.get("type") == "cancel_move_selection":
				self._router.clear_pending_prompt(self._id)
				return None
			if isinstance(spotChoice, dict) and spotChoice.get("type") == "spot_selection" and spotChoice.get("result") in originsById:
				self._router.clear_pending_prompt(self._id)
				return originsById[spotChoice["result"]]

	async def getTargetChoiceFromPlayer(self, possibleTargets, canCancel: bool = False) -> Spot:
		messageKey = "prompts.choose_target"
		fallback = "Where do you want to move this piece?"

		await self.send_message_to_user(build_message("query-target", messageKey, fallback, targetOptions=[str(target) for target in possibleTargets], canCancel=canCancel))

		targetsById = {str(target): target for target in possibleTargets}
		while True:
			spotChoice = await self.get_input_from_prompt(messageKey, fallback)
			if canCancel and isinstance(spotChoice, dict) and spotChoice.get("type") == "cancel_move_selection":
				self._router.clear_pending_prompt(self._id)
				return None
			if isinstance(spotChoice, dict) and spotChoice.get("type") == "spot_selection" and spotChoice.get("result") in targetsById:
				self._router.clear_pending_prompt(self._id)
				return targetsById[spotChoice["result"]]

	async def getSevenStepChoiceFromPlayer(self, options: list[Move]) -> Move:
		if not options:
			raise ValueError("Cannot choose a seven step without any available option")

		if len(options) == 1:
			return options[0]

		possibleOrigins = list(dict.fromkeys(move.originSpot for move in options))

		if len(possibleOrigins) == 1:
			origin = possibleOrigins[0]
		else:
			origin = await self.getOriginChoiceFromPlayer(possibleOrigins)

		possibleTargets = list(dict.fromkeys(move.targetSpot for move in options if move.originSpot == origin))

		if len(possibleTargets) == 1:
			target = possibleTargets[0]
		else:
			target = await self.getTargetChoiceFromPlayer(possibleTargets)

		return next(move for move in options if move.originSpot == origin and move.targetSpot == target)

	def discard(self, card) -> None:
		self._hand.discardFromHand(card)

	async def requestCardExchange(self) -> Card:
		messageKey = "prompts.exchange_card"
		fallback = "Please choose a card to give to your teammate."
		message = build_message("query-card-exchange", messageKey, fallback)

		while True:
			await self.send_message_to_user(message)
			cardChoice = await self._router.wait_for_input(self._id)

			if isinstance(cardChoice, dict) and cardChoice.get("type") == "card_selection":
				chosenCard = Card(cardChoice.get("suit"), cardChoice.get("value"))

				if chosenCard in self._hand.cards:
					break

		self._router.clear_pending_prompt(self._id)
		logger.debug('Card chosen by player for card exchange', extra={'chosenCard': str(chosenCard), 'playerName': self._name})
		return chosenCard

	async def switchCard(self, card1, card2) -> None:
		self._hand.discardFromHand(card1)
		self._hand.addToHand(card2)
		await self.send_message_to_user({"type": "receive-card-from-friend", "value": card2.value, "suit": card2.suit})
		
		givenCard = f"{card1.suit}{card1.value}"
		receivedCard = f"{card2.suit}{card2.value}"

		await self.send_message_to_user(build_message(
			"log",
			"gameplay.card_exchange_complete",
			f"You gave {givenCard} to your teammate and received {receivedCard}. The round will start when the other team finishes exchanging cards.",
			{"givenCard": givenCard, "receivedCard": receivedCard},
		))

	async def forceRandomMove(self) -> None:
		r = random.choice(self.hand.cards)
		while r.value in ['J', '4', '7']:
			r = random.choice(self.hand.cards)
		cmd = json.loads(f'{{"type":"card_selection","name":"{self.name}","value":"{r.value}","suit":"{r.suit}"}}')
		await self._router.add_input(self._id, cmd)

	async def getSevenHopChoiceFromPlayer(self, originSpot: Spot, targetSpot: Spot) -> bool:
		origin = str(originSpot)
		target = str(targetSpot)
		message = build_message("query-seven-hop", "prompts.seven_hop", f"Do you want to seven-hop from {origin} to {target}?", {"origin": origin, "target": target}, origin=origin, target=target)

		while True:
			await self.send_message_to_user(message)
			logger.debug(f"Waiting for seven-hop choice from player...", extra={"playerName": self._name})
			choice = await self._router.wait_for_input(self._id)

			if isinstance(choice, dict) and choice.get("type") == "seven_hop_choice" and isinstance(choice.get("result"), bool):
				self._router.clear_pending_prompt(self._id)
				return choice["result"]
