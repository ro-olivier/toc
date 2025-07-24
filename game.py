from __future__ import annotations

import asyncio
from typing import Optional, Tuple

from board import Board
from cards import Deck
from params import *
from player import Player


class Game:
	def __init__(self, gameSession : GameSession):
		self._gameSession = gameSession
		self._board = Board()
		self._deck = Deck()
		self._isStarted = False
		self._isFinished = False
		self._numPlayers = 0
		self._players = []
		self._handsFinished = 0
		self._activePlayerIndex = -1
		self._activePlayer = None

	def __str__(self) -> str:
		s = f'This game has {self._numPlayers} players.\r\n'
		for i in range(0, self._numPlayers):
			s += f'Player {i} : {str(self._players[i])}'
			s += '\r\n'
		return s

	async def broadcast(self, msg: str):
		await self._gameSession.broadcast(msg)

	def printNumPlayers(self) -> None:
		self.broadcast(f'This game has {self._numPlayers} players.')

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
	def players(self) -> list[Player]:
		return self._players

	@property
	def activePlayer(self) -> Player:
		return self._activePlayer

	def getTeammate(self, player) -> Optional[Player]:
		for player2 in self._players:
			if player2 != player and player2.team == player.team:
				return player2
		return None

	@property
	def dealer(self) -> Player:
		return self._players[0]

	def getPlayersInTeams(self) -> list[Tuple[Player, Player]]:
		seen_players = set()
		res = []
		for player in self._players:
			if player in seen_players:
				continue
			teammate = self.getTeammate(player)
			if teammate and teammate not in seen_players:
				res.append((player, teammate))
				seen_players.add(player)
				seen_players.add(teammate)
		return res

	def resetActivePlayerIndex(self) -> None:
		self._activePlayerIndex = -1

	def setPlayers(self, players : list[Player]) -> None:
		# self._players is an ordered array, where the first element is always the dealer and where the players are always positioned in the order in which they play
		self._numPlayers = len(players)
		self._players = players
		self._players[0].setDealer()
		for player in self._players:
			player.setBoard(self._board) 

	async def nextDealer(self) -> None:
		self._players = self._players[1:] + self._players[:1]
		self._players[0].setDealer()
		await self.broadcast({"type": "dealer", "playerId": self._players[0].name})

	async def drawHands(self, first_round : bool) -> None:
		if first_round:
			for player in self._players:
				hand = self._deck.drawHand(5, player)
				await player.setHand(hand)
		else:
			for player in self._players:
				hand = self._deck.drawHand(4, player)
				await player.setHand(hand)

	async def requestCardExchange(self, players: Tuple[Player, Player]) -> None:
		player1, player2 = players
		card1, card2 = await asyncio.gather(
			player1.requestCardExchange(),
			player2.requestCardExchange()
		)

		await player1.switchCard(card1, card2)
		await player2.switchCard(card2, card1)

	async def runRound(self, round_name : str, first_round : bool) -> None:
		await self.broadcast({"type": "log", "msg": f"Starting {round_name} round with player {self.dealer} as the dealer.\n"})
		self.resetActivePlayerIndex()
		await self.drawHands(first_round)

		teams = self.getPlayersInTeams()
		team0 = teams[0]
		team1 = teams[1]

		await asyncio.gather(
			self.requestCardExchange(team0),
			self.requestCardExchange(team1)
		)

		self._handsFinished = 0
		while self._handsFinished < self._numPlayers:
			await self.nextPlayer()
		await self.broadcast({"type": "log", "msg": f"{round_name} round is finished."})

	async def start(self) -> None:
		self._isStarted = True

		self._players[0].setDealer()
		await self.broadcast({"type": "dealer", "playerId": self._players[0].name})

		while not self._isFinished:
			await self.runRound('First', first_round = True)
			await self.runRound('Second', first_round = False)
			await self.runRound('Third', first_round = False)

			self._deck.reset(self.players)
			self.nextDealer()
			await self.start()

	async def nextPlayer(self) -> None:
		self._activePlayerIndex += 1
		if self._activePlayerIndex == NUMBER_OF_PLAYERS:
			self._activePlayerIndex = 0
		self._activePlayer = self._players[self._activePlayerIndex]

		if self._activePlayer.hand.size > 0:
			await self.broadcast({"type": "next-player", "playerId": self._activePlayer.name, "msg": f"Moving on to next player: {str(self._activePlayer)}"})

			moveOptions = self._activePlayer.hand.getAllPossibleMoves(self._board)
			if len(moveOptions) == 0:
				# player has no available move, he must fold his hand
				await self.broadcast({"type": "fold", "playerId": self._activePlayer.name, "msg": f"Player has no available move and must fold."})
				self._deck.discardCards(self._activePlayer.hand)
				await self._activePlayer.foldHand()
			else:
				if len(moveOptions) == 1:
					# player has only one move and therefore MUST play it
					moveChoice = moveOptions[0]
					moveChoice.updateDescription()
					await self._activePlayer.send_message_to_user({"type": "forced-play", "msg": f"You only have one available move and therefore must play it.", "playerId": self._activePlayer.name, "value": moveChoice.card.value, "suit": moveChoice.card.suit, "origin": str(moveChoice.originSpot), "target": str(moveChoice.targetSpot)})
				else:
					# player has several possible moves and is prompted to select one
					moveChoice = await self._activePlayer.getMoveChoiceFromPlayer(moveOptions)

				cardChoice = moveChoice.card
				await self.broadcast({"type": "play", "msg": f"Player {self._activePlayer.name} has selected the following move: {str(moveChoice)}", "playerId": self._activePlayer.name, "value": moveChoice.card.value, "suit": moveChoice.card.suit, "origin": str(moveChoice.originSpot), "target": str(moveChoice.targetSpot)})

				if moveChoice.ID in ['OUT', 'MOVE', 'SWITCH', 'BACK', 'ENTER']:
					# have the player discard the card from his hand
					self._activePlayer.discard(cardChoice)
					# and put the card in the discard pile of the deck
					self._deck.discardCard(cardChoice)

					origin = self._board.getSpot(moveChoice.originSpot.color, moveChoice.originSpot.number)
					target = self._board.getSpot(moveChoice.targetSpot.color, moveChoice.targetSpot.number)
					
					# player decided to take a piece out
					if moveChoice.ID == 'OUT':
						self._activePlayer.addAPieceOnTheBoard()
						target.setOccupant(self._activePlayer, True)

					# player decided to move a piece forward or backward
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

			await self.broadcast({"type": "log", "msg": f"End of turn for player {self._activePlayer.name}.\n"})
			#await self.broadcast(f'\nState of the board:\n{str(self._board)}')
		else:
			await self.broadcast({"type": "log", "msg": f"Next player: {self._activePlayer.name} has folded in a previous turn, moving on...\n"})


		# When a player manages to fill all his/her houses:
		if self._board.areAllHouseFilled(self._activePlayer.color):
			await self.broadcast({"type": "log", "msg": f"Player {self._activePlayer.name} has filled all houses!)"})

			teammate = self.getTeammate(self._activePlayer)
			# If the teammate's houses are all filled as well, the game is won!
			if self._board.areAllHouseFilled(teammate.color):
				await self.broadcast({"type": "log", "msg": f"Players {self._activePlayer.name} and {teammate.name} win!!!"})
			else:
				await self.broadcast({"type": "log", "msg": f"This player will now play using his/her teammate\'s pieces and attempt to win the game."})
				self._activePlayer.color = self.getTeammate(self._activePlayer).color
