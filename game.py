from __future__ import annotations
from typing import Optional

from board import Board
from move import Move
from cards import Deck
from params import *

class Game:
	def __init__(self):
		self._board = Board()
		self._deck = Deck()
		self._isStarted = False
		self._isFinished = False

	def __str__(self):
		s = f'This game has {self._numPlayers} players.\r\n'
		for i in range(0, self._numPlayers):
			s += f'Player {i} : {str(self._players[i])}'
			s += '\r\n'
		return s

	def printNumPlayers(self):
		print(f'This game has {self._numPlayers} players.')

	@property
	def numPlayers(self) -> int:
		return self._numPlayers

	@property
	def board(self) -> Board:
		return self._board

	@property
	def deck(self) -> Deck:
		return self._deck

	@property
	def isStarted(self) -> bool:
		return self._isStarted

	@property
	def isFinished(self) -> bool:
		return self._isFinished

	@property
	def players(self) -> [Players]:
		return self._players

	@property
	def dealer(self) -> Player:
		return self._players[0]

	def setPlayers(self, players : [Player]) -> None:
		# self._players is an ordered array, where the first element is always the dealer
		self._numPlayers = len(players)
		self._players = players
		self._players[0].setDealer()

	def nextDealer(self) -> None:
		self._players = self._players[1:] + self._players[:1]
		self._players[0].setDealer()

	def drawHands(self, first_round : bool) -> None:
		self._handsFinished = 0
		if first_round:
			for player in self._players:
				hand = self._deck.drawHand(5, player)
				player.setHand(hand)
		else:
			for player in self._players:
				hand = self._deck.drawHand(4, player)
				player.setHand(hand)

	def runRound(self, round_name : str, first_round : bool) -> None:
	    print(f'Starting {round_name} round with dealer {self.dealer}...')
	    self._activePlayerIndex = -1
	    self.drawHands(first_round)
	    self._handsFinished = 0
	    while self._handsFinished < self._numPlayers:
	        self.nextPlayer()
	    print(f'{round_name} round is finished.\n')

	def start(self) -> None:
		self._isStarted = True

		while not self._isFinished:
			self.runRound('First', first_round = True)
			self.runRound('Second', first_round = False)
			self.runRound('Third', first_round = False)

			self._deck.reset()
			self.nextDealer()
			self.start()

	def nextPlayer(self):
		self._activePlayerIndex += 1
		if self._activePlayerIndex == NUMBER_OF_PLAYERS:
			self._activePlayerIndex = 0
		self._activePlayer = self._players[self._activePlayerIndex]

		if self._activePlayer.hand.size > 0:
			print(f'\nMoving on to next player: {str(self._activePlayer)}')

			moveOptions = self._activePlayer.hand.getAllPossibleMoves(self._board)
			if len(moveOptions) == 0:
				# player has no available move, he must fold his hand
				print(f'Player has no available move and must fold.')
				self._activePlayer.hand.fold()
			else:
				if len(moveOptions) == 1:
					# player has only one move and therefore MUST play it
					print(f'Player has only one available move and therefore must play it.')
					moveChoice = moveOptions[0]
					moveChoice.updateDescription()
				else:
					# player has several possible moves and is prompted to select one
					moveChoice = self._activePlayer.getMoveChoiceFromPlayer(moveOptions)

				cardChoice = moveChoice.card
				print(f'Player {self._activePlayer.name} has selected the following move: {str(moveChoice)}')

				if moveChoice.ID in ['OUT', 'MOVE', 'SWITCH', 'BACK', 'ENTER']:
					# have the player discard the card from his hand
					self._activePlayer.discard(cardChoice)
					# and put the card in the discard pile of the deck
					cardChoice.discard()

					origin = self._board.getSpot(moveChoice.originSpot.color, moveChoice.originSpot.number)
					target = self._board.getSpot(moveChoice.targetSpot.color, moveChoice.targetSpot.number)
					
					# player decided to take a piece out
					if moveChoice.ID == 'OUT':
						self._activePlayer.addAPieceOnTheBoard()
						target.setOccupant(self._activePlayer, True)

					# player decided to move a piece foward or backward
					if moveChoice.ID in ['MOVE', 'BACK']:
						origin.setEmpty()
						kickedPlayer = target.setOccupant(self._activePlayer)
						if not kickedPlayer is None:
							kickedPlayer.removeAPieceFromTheBoard()

					# player decided to switch two pieces
					if moveChoice.ID == 'SWITCH':
						origin.setOccupant(moveChoice.targetSpot.occupant)
						target.setOccupant(self._activePlayer)

					# player decided to move a piece into a house
					if moveChoice.ID == 'ENTER':
						# Re-getting the target spot because it's now a house, not a spot !
						target = self._board.getHouse(moveChoice.targetSpot.color, moveChoice.targetSpot.number)
						origin.setEmpty()
						target.setOccupant(self._activePlayer)

				elif moveChoice.ID == 'SEVEN':
					self._activePlayer.getSevenMoveFromPlayer(self._board)

			if self._activePlayer.hand.size == 0:
				self._handsFinished += 1

			print(f'End of turn for player {self._activePlayer.name}.')
			print(f'\nState of the board:\n{str(self._board)}')
		else:
			print(f'\nNext player: {self._activePlayer.name} has folded in a previous turn, moving on...')