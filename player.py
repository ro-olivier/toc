from __future__ import annotations

import random

from cards import Card
from hand import Hand

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
		s = f'{self._name} in team {self._team} playing {self._color}'
		# Commenting out this bit since we probably don't want to keep broadcasting this to all players... 
		# Not sure this will be useful again at some point, I'm keeping it just in case
		#if self._hand:
		#	s+= f' holding the following cards: {self._hand.allCardsString()}'
		return s

	async def send_message_to_user(self, message: str) -> None:
		await self._router.send_output(self._id, message)

	async def get_input_from_prompt(self, prompt: str) -> str:
		await self.send_message_to_user({"type": "query", "msg": prompt})
		print(f"[Player] Waiting for input from {self._name}...")
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

	def setDealer(self) -> None:
		self._isDealer = True

	async def foldHand(self) -> None:
		 self._hand.fold()

	async def getCardChoiceFromPlayer(self) -> Card:
		await self.send_message_to_user({"type": "query-card", "msg": 'What card do you want to play?'})
		cardChoice = await self.get_input_from_prompt('What card do you want to play?')
		while not cardChoice or (not 'type' in cardChoice.keys()) or (cardChoice['type'] != 'card_selection') or (not Card(cardChoice['suit'], cardChoice['value']) in self._hand.cards):
			cardChoice = await self.get_input_from_prompt('What card do you want to play?')
		chosenCard = Card(cardChoice['suit'], cardChoice['value'])
		print(f'Card chosen by {self._name} for his/her next move: {chosenCard}')
		return chosenCard

	async def getMoveChoiceFromPlayer(self, options : list[Move]) -> Move:
		##debug##print(f'{[repr(move) for move in options]}')

		for move in options:
			move.updateDescription()

		cardChoice = await self.getCardChoiceFromPlayer()
		print(f'[getMoveChoiceFromPlayer] selected card: {str(cardChoice)} - {id(cardChoice)} - {type(cardChoice)}')
		moveChoice = None
		## TODO: investigate infinite loop when a player played a not-speacil card with only a 7 remaining, which seem to have triggered an infinite loop (which I didn't screenshot unfortunately...)
		while not moveChoice:
			possibleMoves = [move for move in options if move.card == cardChoice]
			print('[getMoveChoiceFromPlayer] Possible moves:')
			for m in possibleMoves:
				print(f'[getMoveChoiceFromPlayer] {str(m)} ---- origin: {m.originSpot} {id(m.originSpot)}, target: {m.targetSpot} {id(m.targetSpot)}, card: {m.card} {id(m.card)}')
			if len(possibleMoves) == 0:
				await self.send_message_to_user({"type": "reject-card-selection", "msg": f'You cannot play that card right now!'})
				cardChoice = await self.getCardChoiceFromPlayer()
			elif len(possibleMoves) == 1:
				moveChoice = possibleMoves[0]
			else:

				possibleOrigins = list(set([move.originSpot for move in possibleMoves if move.card == cardChoice]))
				if len(possibleOrigins) == 1: # There could be one single origin, but several targets (for example an A being played with only one piece out and no more pieces to take out), and so here we may skip asking the player to choose the origin
					origin = possibleOrigins[0]
				else:
					origin = await self.getOriginChoiceFromPlayer(possibleOrigins)
					while not origin:
						origin = await self.getOriginChoiceFromPlayer(possibleOrigins)

				print(f'[getMoveChoiceFromPlayer] selected originSpot: {str(origin)} - {id(origin)} - {type(origin)}')

				possibleTargets = list(set([move.targetSpot for move in possibleMoves if move.originSpot == origin and move.card == cardChoice]))

				print([str(move.targetSpot) for move in possibleMoves if move.originSpot == origin and move.card == cardChoice])
				if len(possibleTargets) == 1: # There could be only one possible target for several moves from different origins (for example you have two pieces seperated by 4 spots and you have only a 4 and an 8 to play), and se here we may skip asking the player to choose the target
					target = possibleTargets[0]
				else:
					target = await self.getTargetChoiceFromPlayer(possibleTargets)
					while not target:
						target = await self.getTargetChoiceFromPlayer(possibleTargets)

				print(f'[getMoveChoiceFromPlayer] selected targetSpot: {str(target)} - {id(target)} - {type(target)}')
				result = [move for move in possibleMoves if move.originSpot == origin and move.card == cardChoice and move.targetSpot == target]
				print([str(r) for r in result])
				moveChoice = result[0]
			
		return moveChoice

	async def getOriginChoiceFromPlayer(self, possibleOrigins) -> Spot:
		await self.send_message_to_user({"type": "query-origin", "msg": 'What piece do you want to play this card on?', "originOptions": [str(o) for o in possibleOrigins]})
		spotChoice = await self.get_input_from_prompt("What piece do you want to play this card on?")
		while not spotChoice or (not 'type' in spotChoice.keys()) or (spotChoice['type'] != 'spot_selection') or (not (self._board.getSpotById(spotChoice['result']) in self._board.getOccupiedSpotsOnTheBoard(self._name) or (self._board.getSpotById(spotChoice['result']) == self._board.getFirstSpot(self._color)))):
			data = await self.get_input_from_prompt("What piece do you want to play this card on?")
		origin = self._board.getSpotById(spotChoice['result'])
		return origin


	async def getTargetChoiceFromPlayer(self, possibleTargets) -> Spot:
		await self.send_message_to_user({"type": "query-target", "msg": 'Where do you want to move this piece?', "targetOptions": [str(t) for t in possibleTargets]})
		spotChoice = await self.get_input_from_prompt("Where do you want to move this piece?")
		while not spotChoice or  (not 'type' in spotChoice.keys()) or (spotChoice['type'] != 'spot_selection') or not (self._board.getSpotById(spotChoice['result'])):
			spotChoice = await self.get_input_from_prompt("Where do you want to move this piece?")
		target = self._board.getSpotById(spotChoice['result'])
		return target

	async def getSevenMoveFromPlayer(self, board : Board) -> None:
		counter = 0
		moves = []
		board.saveState()
		await self.send_message_to_user({"type": "log", "msg": 'Please select the moves you want to do in your seven-split:'})
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
		cardChoice = await self.get_input_from_prompt('Please choose a card to give to your team-mate.')
		while not cardChoice or (not 'type' in cardChoice.keys()) or (cardChoice['type'] != 'card_selection') or (not Card(cardChoice['suit'], cardChoice['value']) in self._hand.cards):
			cardChoice = await self.get_input_from_prompt('Please choose a card to give to your team-mate.')
		chosenCard = Card(cardChoice['suit'], cardChoice['value'])
		print(f'Card chosen by {self._name} for card exchange: {chosenCard}')
		return chosenCard

	async def switchCard(self, card1, card2) -> None:
		self._hand.discardFromHand(card1)
		self._hand.addToHand(card2)
		await self.send_message_to_user({"type": "receive-card-from-friend", "value": card2.value, "suit": card2.suit})
		await self.send_message_to_user({"type": "log", "msg": f"Successfully given {card1.suit}{card1.value} to your team-mate who has given you {card2.suit}{card2.value} in exchange. Round will start as soon as the other team exchanges cards.\n"})

	async def forceRandomMove(self) -> None:
		r = random.choice(self.hand.cards)
		while r.value in ['J', '4', '7']:
			r = random.choice(self.hand.cards)
		cmd = json.loads(f'{{"type":"card_selection","name":"{self.name}","value":"{r.value}","suit":"{r.suit}"}}')
		await self._router.add_input(self._id, cmd)
