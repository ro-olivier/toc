from __future__ import annotations

from cards import Card
from hand import Hand


class Player:
	def __init__(self, name : str, team : str, color : str):
		self._name = name
		self._team = team
		self._color = color
		self._hand = None
		self._active = False
		self._isDealer = False
		self._piecesOnTheBoard = 0

	def __str__(self) -> str:
		s = f'{self._name} in team {self._team} playing {self._color}'
		if self._hand:
			s+= f' holding the following cards: {self._hand.allCardsString()}'
		return s

	@property
	def name(self) -> str:
		return self._name

	@property
	def team(self) -> str:
		return self._team

	@property
	def color(self) -> str:
		return self._color

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

	def setHand(self, hand : Hand):
		self._hand = hand

	def setDealer(self):
		self._isDealer = True

	def getCardChoiceFromPlayer(self) -> Card:
		choice = self._hand.getCard(input('What card do you want to play?\t'))
		while choice is None:
			print(f'Please input a number between 0 and {self._hand.size - 1} to select an available card from your hand.')
			choice = self._hand.getCard(input('What card do you want to play?\t'))
		return choice


	def getMoveChoiceFromPlayer(self, options : list[Move]) -> Move:
		##debug##print(f'{[repr(move) for move in options]}')
		for move in options:
			move.updateDescription()

		for index,option in enumerate(options):
			print(f'{str(index)} -- {str(option)}')

		choice = input('What move do you want to play?\t')
		while choice not in [str(i) for i in range(len(options))]:
			print(f'Please input a number between 0 and {len(options) - 1} to select an available move.')
			choice = input('What move do you want to play?\t')
		return options[int(choice)]

	def getSevenMoveFromPlayer(self, board : Board) -> None:
		counter = 0
		moves = []
		board.saveState()
		print('Print select the moves you want to do in your seven-split:')
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
		print(f'Selected moves for seven split : {moves}')
		confirmation = input('Please confirm that you wish to do this seven-split this way? (Y/N) ')
		while confirmation not in ['Y', 'N']:
			confirmation = input('Please confirm that you wish to do this seven-split this way? (Y/N) ')
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
			self.getSevenMoveFromPlayer(board)

	def discard(self, card) -> None:
		self._hand.discardFromHand(card)