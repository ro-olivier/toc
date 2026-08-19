from __future__ import annotations

import asyncio
from typing import Optional, Tuple

from board import Board
from cards import Deck, Card
from hand import Hand
from params import *
from player import Player
from move import Move
from rules import FiveHopDecider, GameRules, MONTSURVENT_RULES, SevenHopping


class Game:
	def __init__(self, gameSession : GameSession, colors : List, rules: GameRules = MONTSURVENT_RULES):
		self._gameSession = gameSession
		self._rules = rules
		self._board = Board(colors, rules)
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
	def rules(self) -> GameRules:
		return self._rules

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

	def getControlledPlayer(self, player: Player) -> Player:
		teammate = self.getTeammate(player)

		if teammate is not None and self._board.areAllHouseFilled(player.color):
			return teammate

		return player

	def getWinningTeam(self) -> Optional[Tuple[Player, Player]]:
		for team in self.getPlayersInTeams():
			if all(self._board.areAllHouseFilled(player.color) for player in team):
				return team

		return None

	async def finishGameIfWon(self) -> bool:
		winningTeam = self.getWinningTeam()

		if winningTeam is None:
			return False

		self._isFinished = True
		winnerNames = [player.name for player in winningTeam]

		await self.broadcast({"type": "game-over", "winners": winnerNames, "msg": f"Players {' and '.join(winnerNames)} win!"})
		return True

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
		self._activePlayerIndex = 0
		self._activePlayer = None

	def advanceActivePlayer(self) -> Player:
		if not self._players:
			raise RuntimeError("Cannot select an active player before players have joined")

		self._activePlayerIndex = (self._activePlayerIndex + 1) % self._numPlayers
		self._activePlayer = self._players[self._activePlayerIndex]

		return self._activePlayer

	def setPlayers(self, players : list[Player]) -> None:
		# self._players is an ordered array, where the first element is always the dealer and where the players are always positioned in the order in which they play
		self._numPlayers = len(players)
		self._players = players
		self._players[0].setDealer()
		for player in self._players:
			player.setBoard(self._board) 

	async def nextDealer(self) -> None:
		self._players[0].setDealer(False)
		self._players = self._players[1:] + self._players[:1]
		self._players[0].setDealer()
		await self.broadcast({"type": "dealer", "playerId": self._players[0].name})

	async def drawHands(self, cardsPerPlayer: int) -> None:
		cardsByPlayer = {player: [] for player in self._players}
		dealOrder = self._players[1:] + self._players[:1]

		for _ in range(cardsPerPlayer):
			for player in dealOrder:
				cardsByPlayer[player].append(self._deck.drawCard())

		for player in self._players:
			await player.setHand(Hand(player, cardsByPlayer[player]))

	async def requestCardExchange(self, players: Tuple[Player, Player]) -> None:
		player1, player2 = players
		card1, card2 = await asyncio.gather(
			player1.requestCardExchange(),
			player2.requestCardExchange()
		)

		await player1.switchCard(card1, card2)
		await player2.switchCard(card2, card1)

	async def runRound(self, roundName: str, cardsPerPlayer: int) -> None:
		await self.broadcast({"type": "log", "msg": f"Starting {roundName} with player {self.dealer} as the dealer.\n"})
		self.resetActivePlayerIndex()
		await self.drawHands(cardsPerPlayer)

		teams = self.getPlayersInTeams()
		await asyncio.gather(*(self.requestCardExchange(team) for team in teams))

		self._handsFinished = 0

		while self._handsFinished < self._numPlayers and not self._isFinished:
			await self.nextPlayer()

		await self.broadcast({"type": "log", "msg": f"{roundName} is finished."})

	async def runDeckCycle(self) -> None:
		for roundNumber, cardsPerPlayer in enumerate(DEAL_CARD_COUNTS, start=1):
			await self.runRound(f"Deal {roundNumber}", cardsPerPlayer)

			if self._isFinished:
				return

	async def start(self) -> None:
		self._isStarted = True
		self._players[0].setDealer()
		await self.broadcast({"type": "dealer", "playerId": self._players[0].name})

		while not self._isFinished:
			await self.runDeckCycle()

			if not self._isFinished:
				self._deck.recycleDiscardPile()
				await self.nextDealer()

	def applyMove(self, move: Move) -> None:
		origin = move.originSpot
		target = move.targetSpot

		if move.ID == "OUT":
			kickedPlayer = target.setOccupant(move.pieceOwner, True)
			move.pieceOwner.addAPieceOnTheBoard()

			if kickedPlayer is not None:
				kickedPlayer.removeAPieceFromTheBoard()

		elif move.ID in ["MOVE", "BACK", "FIVE", "HOP"]:
			origin.setEmpty()
			kickedPlayer = target.setOccupant(move.pieceOwner)

			if kickedPlayer is not None:
				kickedPlayer.removeAPieceFromTheBoard()

		elif move.ID == "SWITCH":
			targetPlayer = target.occupant
			origin.setOccupant(targetPlayer)
			target.setOccupant(move.pieceOwner)

		elif move.ID == "ENTER":
			origin.setEmpty()
			target.setOccupant(move.pieceOwner)

		else:
			raise ValueError(f"Cannot apply move of type {move.ID}")

	async def playSeven(self, player: Player, pieceOwner: Player = None) -> None:
		pieceOwner = pieceOwner if pieceOwner is not None else player

		for stepsRemaining in range(7, 0, -1):
			options = self._board.getSevenStepOptions(player, stepsRemaining, pieceOwner)

			if not options:
				raise RuntimeError("Seven split reached a state with no complete legal continuation")

			move = await player.getSevenStepChoiceFromPlayer(options)
			self.applyMove(move)

			await self.broadcast({"type": "seven-step", "playerId": player.name, "movedPlayerId": move.pieceOwner.name, "origin": str(move.originSpot), "target": str(move.targetSpot), "stepsRemaining": stepsRemaining - 1})

			if stepsRemaining == 1:
				await self.playSevenHop(move)

	async def playSevenHop(self, triggeringMove: Move) -> Optional[Move]:
		if self._rules.seven_hopping is SevenHopping.DISABLED:
			return None

		hopMove = self._board.getSevenHopMove(triggeringMove)
		if hopMove is None:
			return None

		if self._rules.seven_hopping is SevenHopping.OPTIONAL:
			decidingPlayer = triggeringMove.player

			if triggeringMove.ID == "FIVE" and self._rules.five_hop_decider is FiveHopDecider.PIECE_OWNER:
				decidingPlayer = triggeringMove.pieceOwner

			if not await decidingPlayer.getSevenHopChoiceFromPlayer(hopMove.originSpot, hopMove.targetSpot):
				return None

		self.applyMove(hopMove)
		await self.broadcast({"type": "seven-hop", "playerId": hopMove.player.name, "movedPlayerId": hopMove.pieceOwner.name, "origin": str(hopMove.originSpot), "target": str(hopMove.targetSpot)})
		return hopMove

	async def nextPlayer(self) -> None:
		self.advanceActivePlayer()

		if self._activePlayer.hand.size > 0:
			await self.broadcast({"type": "next-player", "playerId": self._activePlayer.name, "msg": f"Moving on to next player: {str(self._activePlayer)}"})

			controlledPlayer = self.getControlledPlayer(self._activePlayer)
			moveOptions = self._activePlayer.hand.getAllPossibleMoves(self._board, controlledPlayer)

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

				self._activePlayer.discard(cardChoice)
				self._deck.discardCard(cardChoice)

				if moveChoice.ID == "SEVEN":
					await self.broadcast({
						"type": "seven-start",
						"msg": f"Player {self._activePlayer.name} is starting a seven split.",
						"playerId": self._activePlayer.name,
						"value": cardChoice.value,
						"suit": cardChoice.suit,
					})

					await self.resolveMove(moveChoice)

				else:
					await self.broadcast({
						"type": "play",
						"msg": f"Player {self._activePlayer.name} has selected the following move: {str(moveChoice)}",
						"playerId": self._activePlayer.name,
						"value": cardChoice.value,
						"suit": cardChoice.suit,
						"origin": str(moveChoice.originSpot),
						"target": str(moveChoice.targetSpot),
						"movedPlayerId": moveChoice.pieceOwner.name,
					})

					await self.resolveMove(moveChoice)

			if self._activePlayer.hand.size == 0:
				self._handsFinished += 1

			await self.broadcast({"type": "log", "msg": f"End of turn for player {self._activePlayer.name}.\n"})
			#await self.broadcast(f'\nState of the board:\n{str(self._board)}')
		else:
			await self.broadcast({"type": "log", "msg": f"Next player: {self._activePlayer.name} has folded in a previous turn, moving on...\n"})


	async def resolveMove(self, move: Move) -> None:
		if move.ID == "SEVEN":
			await self.playSeven(move.player, move.pieceOwner)
		else:
			self.applyMove(move)
			await self.playSevenHop(move)

		await self.finishGameIfWon()
