from __future__ import annotations

from cards import Card
from hand import Hand

import json


class Player:
	def __init__(self, name : str, team : str = None, color : str = None, position : str = None, gameSession = None, router = None):
		self._name = name
		self._team = team
		self._color = color
		self._position = position
		self._hand = None
		self._active = False
		self._isDealer = False
		self._piecesOnTheBoard = 0
		self._gameSession = gameSession
		self._router = router

	def __str__(self) -> str:
		s = f'{self._name} in team {self._team} playing {self._color}'
		if self._hand:
			s+= f' holding the following cards: {self._hand.allCardsString()}'
		return s

	async def send_message_to_user(self, message: str) -> None:
		await self._router.send_output(self._name, message)

	async def get_input_from_prompt(self, prompt: str) -> str:
		await self.send_message_to_user({"type": "query", "msg": prompt})
		print(f"[Player] Waiting for input from {self._name}...")
		return await self._router.wait_for_input(self._name)
		
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

	async def setHand(self, hand : Hand) -> None:
		self._hand = hand
		await self.send_message_to_user({"type": "draw", "playerId": self._name, "cards": [c.json for c in self._hand.cards]})

	def setDealer(self) -> None:
		self._isDealer = True

	async def getCardChoiceFromPlayer(self) -> Card:
		choice = await self._hand.getCard(self.get_input_from_prompt('What card do you want to play?'))
		while choice is None:
			await self.send_message_to_user({"type": "log", "msg": f'Please input a number between 0 and {self._hand.size - 1} to select an available card from your hand.'})
			choice = await self._hand.getCard(self.get_input_from_prompt('What card do you want to play?'))
		return choice

	async def getMoveChoiceFromPlayer(self, options : list[Move]) -> Move:
		##debug##print(f'{[repr(move) for move in options]}')
		for move in options:
			move.updateDescription()

		for index,option in enumerate(options):
			print(f'{str(index)} -- {str(option)}')

		choice = await self.get_input_from_prompt('What move do you want to play?')
		while choice not in [str(i) for i in range(len(options))]:
			await self.send_message_to_user({"type": "log", "msg": f'Please input a number between 0 and {len(options) - 1} to select an available move.'})
			choice = await self.get_input_from_prompt('What move do you want to play?')
		return options[int(choice)]

	async def getSevenMoveFromPlayer(self, board : Board) -> None:
		counter = 0
		moves = []
		board.saveState()
		await self.send_message_to_user({"type": "log", "msg": 'Print select the moves you want to do in your seven-split:'})
		# This loop will display all the 'one-move' options to the user, who will have to choose one seven times
		while counter < 7:
			moveOptions = board.getMoveOptions(self, Card('', '1'))
			##debug##print(f'moveOptions provided to user : {moveOptions}')
			moveChoice = self.getMoveChoiceFromPlayer(moveOptions)

			# the move effect on the board are applied as if the move was really going to happen, but it's ok since the board.saveState() was called earlier
			# and so the board can be restored later
			moveChoice.originSpot.setEmpty()
			moveChoice.targetSpot.setOccupant(self)
			# we don't actually kick the users from the spots they occupy because that would mess up the pieceOnTheBoard counter
			# we store the move and go on seven times
			moves.append(moveChoice)
			counter += 1
		await self.send_message_to_user({"type": "log", "msg": f'Selected moves for seven split : {moves}'})
		confirmation = await self.get_input_from_prompt('Please confirm that you wish to do this seven-split this way? (Y/N) ')
		while confirmation not in ['Y', 'N']:
			confirmation = await self.get_input_from_prompt('Please confirm that you wish to do this seven-split this way? (Y/N) ')
		# we restore the board state before re-applying all the changes, but this time kicking player along the way
		board.restoreState()
		# if the user confirms we proceed
		if confirmation == 'Y':
			for move in moves:
				board.getSpot(move.originSpot.color, move.originSpot.number).setEmpty()
				kickedPlayer = board.getSpot(move.targetSpot.color, move.targetSpot.number).setOccupant(self)
				if not kickedPlayer is None:
					kickedPlayer.removeAPieceFromTheBoard()
		# if the user does not confirm we simply call the method again to offer the possibility to choose differently
		# (the board was already restored so we're good)
		else:
			await self.getSevenMoveFromPlayer(board)

	def discard(self, card) -> None:
		self._hand.discardFromHand(card)

	async def requestCardExchange(self) -> Card:
		#await self.send_message_to_user({"type": "log", "msg": f'Player {self._name}, here are the cards in your hand: {"  ||  ".join([str(index) + " - " + str(card) for index,card in enumerate(self._hand.cards)])}'})
		cardChoice = await self.get_input_from_prompt('Please choose a card to give to your team-mate.')
		while not cardChoice or (not 'type' in cardChoice.keys()) or (cardChoice['type'] != 'card_selection') or (not Card(cardChoice['suit'], cardChoice['value']) in self._hand.cards):
			cardChoice = await self.get_input_from_prompt('Please choose a card to give to your team-mate.')
		chosenCard = Card(cardChoice['suit'], cardChoice['value'])
		print(f'Card chosen by {self._name} for card exchange: {chosenCard}')
		return chosenCard

	async def switchCard(self, card1, card2) -> None:
		self._hand.discardFromHand(card1)
		await self.send_message_to_user({"type": "discard_card", "playerId": self._name, "value": card1.value, "suit": card1.suit})
		self._hand.addToHand(card2)
		await self.send_message_to_user({"type": "add_card", "playerId": self._name, "value": card2.value, "suit": card2.suit})