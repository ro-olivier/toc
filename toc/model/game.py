from __future__ import annotations

import asyncio
from typing import Optional, Tuple

from toc.model.board import Board
from toc.model.cards import Deck, Card
from toc.model.hand import Hand
from toc.model.spot import Spot
from toc.model.params import *
from toc.model.player import Player
from toc.model.move import Move
from toc.model.rules import *
from toc.model.game_phase import GamePhase
from toc.infrastructure.messages import build_message
import logging

logger = logging.getLogger("toc.game")


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
		self._dealerRotationCount = 0

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

	@property
	def handsFinished(self) -> int:
		return self._handsFinished

	@property
	def activePlayerIndex(self) -> int:
		return self._activePlayerIndex

	@property
	def dealerRotationCount(self) -> int:
		return self._dealerRotationCount

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
		if self._isFinished:
			return True
		
		winningTeam = self.getWinningTeam()

		if winningTeam is None:
			return False

		self._isFinished = True
		winnerNames = [player.name for player in winningTeam]
		playerOne, playerTwo = winnerNames

		await self.broadcast(build_message(
			"game-over",
			"gameplay.team_won",
			f"{playerOne} and {playerTwo} win!",
			{"playerOne": playerOne, "playerTwo": playerTwo},
			winners=winnerNames,
		))
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

		rotationStep = 1 if self._rules.rotation is Rotation.CLOCKWISE else -1
		self._activePlayerIndex = (self._activePlayerIndex + rotationStep) % self._numPlayers
		self._activePlayer = self._players[self._activePlayerIndex]

		return self._activePlayer

	def setPlayers(self, players : list[Player]) -> None:
		# self._players is ordered clockwise around the board, with the dealer first.
		self._numPlayers = len(players)
		self._players = players
		self._players[0].setDealer()
		for player in self._players:
			player.setBoard(self._board)

	def restoreRuntimeState(self, deck: Deck, isStarted: bool, isFinished: bool, handsFinished: int, activePlayerIndex: int, activePlayer: Optional[Player], dealerRotationCount: int) -> None:
		self._deck = deck
		self._isStarted = isStarted
		self._isFinished = isFinished
		self._handsFinished = handsFinished
		self._activePlayerIndex = activePlayerIndex
		self._activePlayer = activePlayer
		self._dealerRotationCount = dealerRotationCount

	async def nextDealer(self) -> None:
		self._players[0].setDealer(False)
		
		if self._rules.rotation is Rotation.CLOCKWISE:
			self._players = self._players[1:] + self._players[:1]
		else:
			self._players = self._players[-1:] + self._players[:-1]

		self._players[0].setDealer()
		self._dealerRotationCount += 1
		
		await self.broadcast({"type": "dealer", "playerId": self._players[0].name})

	def shouldShuffleRecycledDeck(self) -> bool:
		if self._rules.shuffle_cards is ShuffleMode.ON_DEALER_CHANGE:
			return True

		if self._rules.shuffle_cards is ShuffleMode.ON_DEALER_CYCLE:
			rotationCountAfterDealerChange = self._dealerRotationCount + 1
			return self._numPlayers > 0 and rotationCountAfterDealerChange % self._numPlayers == 0

		return False

	async def drawHands(self, cardsPerPlayer: int) -> None:
		cardsByPlayer = {player: [] for player in self._players}
		if self._rules.rotation is Rotation.CLOCKWISE:
			dealOrder = self._players[1:] + self._players[:1]
		else:
			dealOrder = list(reversed(self._players[1:])) + self._players[:1]

		for _ in range(cardsPerPlayer):
			for player in dealOrder:
				cardsByPlayer[player].append(self._deck.drawCard())

		for player in self._players:
			await player.setHand(Hand(player, cardsByPlayer[player]))

	async def requestCardExchange(self, players: Tuple[Player, Player]) -> tuple[Player, Card, Player, Card]:
		player1, player2 = players

		card1, card2 = await asyncio.gather(
			player1.requestCardExchange(),
			player2.requestCardExchange(),
		)

		return player1, card1, player2, card2

	async def exchangeCards(self) -> None:
		exchanges = await asyncio.gather(*(self.requestCardExchange(team) for team in self.getPlayersInTeams()))

		for player1, card1, player2, card2 in exchanges:
			await asyncio.gather(
				player1.switchCard(card1, card2),
				player2.switchCard(card2, card1),
			)

	async def runRound(self, dealNumber: int, cardsPerPlayer: int) -> None:
		dealIndex = dealNumber - 1
		self._gameSession.setGamePhase(GamePhase.DEAL_START, dealIndex)
		await self._gameSession.checkpointActive()

		await self.broadcast(build_message("log", "gameplay.deal_started", f"Deal {dealNumber} starts with {self.dealer.name} as dealer.", {"deal": dealNumber, "dealer": self.dealer.name}))
		self.resetActivePlayerIndex()

		await self.drawHands(cardsPerPlayer)
		self._handsFinished = 0

		if self._rules.card_exchange:
			self._gameSession.setGamePhase(GamePhase.CARD_EXCHANGE, dealIndex)
			await self._gameSession.checkpointActive()
			await self.exchangeCards()

		self._gameSession.setGamePhase(GamePhase.TURN_START, dealIndex)
		await self._gameSession.checkpointActive()

		while self._handsFinished < self._numPlayers and not self._isFinished:
			await self.nextPlayer()

		self._gameSession.setGamePhase(GamePhase.DEAL_END, dealIndex)
		await self._gameSession.checkpointActive()

		await self.broadcast(build_message("log", "gameplay.deal_finished", f"Deal {dealNumber} is finished.", {"deal": dealNumber}))

	async def runDeckCycle(self) -> None:
		for roundNumber, cardsPerPlayer in enumerate(self._rules.deal_card_counts, start=1):
			await self.runRound(roundNumber, cardsPerPlayer)

			if self._isFinished:
				return

		self._gameSession.setGamePhase(GamePhase.DECK_CYCLE_END, len(self._rules.deal_card_counts) - 1)
		await self._gameSession.checkpointActive()

	async def start(self) -> None:
		self._isStarted = True
		self._players[0].setDealer()
		await self.broadcast({"type": "dealer", "playerId": self._players[0].name})

		while not self._isFinished:
			await self.runDeckCycle()

			if not self._isFinished:
				self._deck.recycleDiscardPile(shuffle=self.shouldShuffleRecycledDeck())
				await self.nextDealer()
				self._gameSession.setGamePhase(GamePhase.DEAL_START, 0)
				await self._gameSession.checkpointActive()

	def applyMove(self, move: Move) -> list:
		origin = move.originSpot
		target = move.targetSpot

		pathKickPositions = []

		if self._rules.king_kicks_pieces_on_path and move.card is not None and move.card.value == "K" and move.ID in ["MOVE", "ENTER"]:
			for position in self._board.getPositionsCrossedByMove(move):
				if position.isOccupied:
					kickedPlayer = position.occupant
					position.setEmpty()
					kickedPlayer.removeAPieceFromTheBoard()
					pathKickPositions.append(position)

		if move.ID == "OUT":
			kickedPlayer = target.setOccupant(move.pieceOwner, isOwnPlayerTakingAPieceOut=True, isBlocking=self._rules.exit_spot_is_protected_and_blocking)
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
			kickedPlayer = target.setOccupant(move.pieceOwner)

			if kickedPlayer is not None:
				kickedPlayer.removeAPieceFromTheBoard()

		else:
			raise ValueError(f"Cannot apply move of type {move.ID}")

		return pathKickPositions

	async def playSeven(self, player: Player, pieceOwner: Player = None, card: Card = None, stepsRemaining: int = 7, movedPiecePositions: set[Spot] = None) -> None:
		pieceOwner = pieceOwner if pieceOwner is not None else player

		if not self._rules.seven_split_kicks_pieces_on_path:
			await self.playSevenWithoutPathKicks(player, pieceOwner, card, stepsRemaining, movedPiecePositions)
			return

		for currentStepsRemaining in range(stepsRemaining, 0, -1):
			options = self._board.getSevenStepOptions(player, currentStepsRemaining, pieceOwner)

			if not options:
				raise RuntimeError("Seven split reached a state with no complete legal continuation")

			move = await player.getSevenStepChoiceFromPlayer(options)
			self.applyMove(move)
			nextStepsRemaining = currentStepsRemaining - 1

			if nextStepsRemaining > 0:
				self._gameSession.updateSevenSplit(nextStepsRemaining)
				await self._gameSession.checkpointActive()
			else:
				self._gameSession.setGamePhase(GamePhase.TURN_END)

			await self.broadcast({
				"type": "seven-step",
				"playerId": player.name,
				"movedPlayerId": move.pieceOwner.name,
				"origin": str(move.originSpot),
				"target": str(move.targetSpot),
				"stepsRemaining": nextStepsRemaining,
			})

			if nextStepsRemaining == 0:
				await self.playSevenHop(move, card)

	async def playSevenWithoutPathKicks(self, player: Player, pieceOwner: Player, card: Card = None, stepsRemaining: int = 7, movedPiecePositions: set[Spot] = None) -> None:
		movedPiecePositions = set() if movedPiecePositions is None else set(movedPiecePositions)
		lastMove = None

		while stepsRemaining > 0:
			options = self._board.getSevenAllocationOptions(player, stepsRemaining, pieceOwner, movedPiecePositions)

			if not options:
				raise RuntimeError("Seven split reached a state with no complete legal continuation")

			move = await player.getSevenStepChoiceFromPlayer(options)
			self.applyMove(move)
			stepsRemaining -= move.steps
			movedPiecePositions.add(move.targetSpot)
			lastMove = move

			if stepsRemaining > 0:
				positionIds = tuple(sorted(str(position) for position in movedPiecePositions))
				self._gameSession.updateSevenSplit(stepsRemaining, positionIds)
				await self._gameSession.checkpointActive()
			else:
				self._gameSession.setGamePhase(GamePhase.TURN_END)

			await self.broadcast({
				"type": "seven-step",
				"playerId": player.name,
				"movedPlayerId": move.pieceOwner.name,
				"origin": str(move.originSpot),
				"target": str(move.targetSpot),
				"stepsUsed": move.steps,
				"stepsRemaining": stepsRemaining,
			})

		if lastMove is not None:
			await self.playSevenHop(lastMove, card)

	async def playSevenHop(self, triggeringMove: Move, playedCard: Card = None) -> Optional[Move]:
		if self._rules.seven_hopping is SevenHopping.DISABLED:
			return None

		hopMove = self._board.getSevenHopMove(triggeringMove)

		if hopMove is None:
			return None

		if self._rules.seven_hopping is SevenHopping.OPTIONAL:
			decidingPlayer = triggeringMove.player

			if triggeringMove.ID == "FIVE" and self._rules.five_hop_decider is FiveHopDecider.PIECE_OWNER:
				decidingPlayer = triggeringMove.pieceOwner

			self._gameSession.beginSevenHop(hopMove, decidingPlayer, playedCard)
			await self._gameSession.checkpointActive()
			return await self.completeOptionalSevenHop(hopMove, decidingPlayer)

		self.applyMove(hopMove)
		self._gameSession.setGamePhase(GamePhase.TURN_END)
		await self._gameSession.checkpointActive()

		await self.broadcast({
			"type": "seven-hop",
			"playerId": hopMove.player.name,
			"movedPlayerId": hopMove.pieceOwner.name,
			"origin": str(hopMove.originSpot),
			"target": str(hopMove.targetSpot),
		})

		return hopMove

	async def completeOptionalSevenHop(self, hopMove: Move, decidingPlayer: Player) -> Optional[Move]:
		if not await decidingPlayer.getSevenHopChoiceFromPlayer(hopMove.originSpot, hopMove.targetSpot):
			self._gameSession.setGamePhase(GamePhase.TURN_END)
			await self._gameSession.checkpointActive()
			return None

		self.applyMove(hopMove)
		self._gameSession.setGamePhase(GamePhase.TURN_END)
		await self._gameSession.checkpointActive()

		await self.broadcast({
			"type": "seven-hop",
			"playerId": hopMove.player.name,
			"movedPlayerId": hopMove.pieceOwner.name,
			"origin": str(hopMove.originSpot),
			"target": str(hopMove.targetSpot),
		})

		return hopMove

	async def nextPlayer(self) -> None:
		self.advanceActivePlayer()
		self._gameSession.setGamePhase(GamePhase.TURN_DECISION)
		await self._gameSession.checkpointActive()
		await self.playCurrentTurn()

	async def playCurrentTurn(self) -> None:

		if self._activePlayer.hand.size > 0:
			await self.broadcast(build_message(
				"next-player",
				"gameplay.next_player",
				f"Moving on to {self._activePlayer.name} from team {self._activePlayer.team}, playing {self._activePlayer.color}.",
				{"player": self._activePlayer.name, "team": self._activePlayer.team, "color": self._activePlayer.color},
				playerId=self._activePlayer.name,
			))

			controlledPlayer = self.getControlledPlayer(self._activePlayer)
			moveOptions = self._activePlayer.hand.getAllPossibleMoves(self._board, controlledPlayer)

			if len(moveOptions) == 0:
				if self._rules.cannot_play_folds_entire_hand:
					await self.broadcast(build_message(
						"fold",
						"gameplay.player_folded",
						f"{self._activePlayer.name} has no available move and must fold.",
						{"player": self._activePlayer.name},
						playerId=self._activePlayer.name,
					))
					self._deck.discardCards(self._activePlayer.hand)
					await self._activePlayer.foldHand()
				else:
					cardChoice = await self._activePlayer.getCardChoiceFromPlayer("prompts.discard_card", "You cannot make a move. Choose one card to discard.")
					self._activePlayer.discard(cardChoice)
					self._deck.discardCard(cardChoice)
					await self.broadcast(build_message(
						"discard",
						"gameplay.card_discarded",
						f"{self._activePlayer.name} cannot make a move and discards one card.",
						{"player": self._activePlayer.name},
						playerId=self._activePlayer.name,
						value=cardChoice.value,
						suit=cardChoice.suit,
					))
			else:
				if len(moveOptions) == 1:
					# player has only one move and therefore MUST play it
					moveChoice = moveOptions[0]
					moveChoice.updateDescription()
					cardLabel = f"{moveChoice.card.suit}{moveChoice.card.value}"
					await self._activePlayer.send_message_to_user(build_message(
						"forced-play",
						"gameplay.forced_play",
						f"You have only one legal move, so you must play {cardLabel}.",
						{"card": cardLabel},
						playerId=self._activePlayer.name,
						value=moveChoice.card.value,
						suit=moveChoice.card.suit,
						origin=str(moveChoice.originSpot),
						target=str(moveChoice.targetSpot),
					))
				else:
					# player has several possible moves and is prompted to select one
					moveChoice = await self._activePlayer.getMoveChoiceFromPlayer(moveOptions)

				cardChoice = moveChoice.card

				self._activePlayer.discard(cardChoice)
				self._deck.discardCard(cardChoice)

				if moveChoice.ID == "SEVEN":
					cardLabel = f"{cardChoice.suit}{cardChoice.value}"

					await self.broadcast(build_message(
						"seven-start",
						"gameplay.seven_split_started",
						f"{self._activePlayer.name} played {cardLabel} and is starting a seven split.",
						{"player": self._activePlayer.name, "card": cardLabel},
						playerId=self._activePlayer.name,
						value=cardChoice.value,
						suit=cardChoice.suit,
					))

					await self.resolveMove(moveChoice)

				else:
					cardLabel = f"{cardChoice.suit}{cardChoice.value}"
					origin = str(moveChoice.originSpot)
					target = str(moveChoice.targetSpot)

					eventPayload = {
						"playerId": self._activePlayer.name,
						"value": cardChoice.value,
						"suit": cardChoice.suit,
						"origin": origin,
						"target": target,
						"movedPlayerId": moveChoice.pieceOwner.name,
					}

					if moveChoice.ID == "OUT":
						message = build_message(
							"play",
							"gameplay.piece_deployed",
							f"{self._activePlayer.name} played {cardLabel} and deployed a piece on {target}.",
							{"player": self._activePlayer.name, "card": cardLabel, "target": target},
							**eventPayload,
						)

					elif moveChoice.ID == "SWITCH":
						message = build_message(
							"play",
							"gameplay.pieces_switched",
							f"{self._activePlayer.name} played {cardLabel} and switched the pieces on {origin} and {target}.",
							{"player": self._activePlayer.name, "card": cardLabel, "origin": origin, "target": target},
							**eventPayload,
						)

					else:
						message = build_message(
							"play",
							"gameplay.piece_moved",
							f"{self._activePlayer.name} played {cardLabel}, moving {moveChoice.pieceOwner.name}'s piece from {origin} to {target}.",
							{"player": self._activePlayer.name, "card": cardLabel, "pieceOwner": moveChoice.pieceOwner.name, "origin": origin, "target": target},
							**eventPayload,
						)

					await self.broadcast(message)

					await self.resolveMove(moveChoice)

			self._gameSession.setGamePhase(GamePhase.TURN_END)
			await self._gameSession.checkpointActive()
			await self.finishCurrentTurn()
		else:
			await self.finishCurrentTurn(skipped=True)


	async def finishCurrentTurn(self, skipped: bool = False) -> None:
		if await self.finishGameIfWon():
			return

		self._handsFinished = sum(player.hand.size == 0 for player in self._players)
		self._gameSession.setGamePhase(GamePhase.TURN_START)
		await self._gameSession.checkpointActive()

		if skipped:
			await self.broadcast(build_message(
				"log",
				"gameplay.folded_player_skipped",
				f"{self._activePlayer.name} previously folded and is skipped.",
				{"player": self._activePlayer.name},
			))
			return

		await self.broadcast(build_message(
			"log",
			"gameplay.turn_ended",
			f"{self._activePlayer.name}'s turn is finished.",
			{"player": self._activePlayer.name},
		))

	async def resolveMove(self, move: Move) -> None:
		if move.ID == "SEVEN":
			self._gameSession.beginSevenSplit(move)
			await self._gameSession.checkpointActive()
			await self.playSeven(move.player, move.pieceOwner, move.card)
		else:
			pathKickPositions = self.applyMove(move)

			if pathKickPositions:
				await self.broadcast({"type": "path-kicks", "positions": [str(position) for position in pathKickPositions]})

			await self.playSevenHop(move)

		self._gameSession.setGamePhase(GamePhase.TURN_END)
		await self._gameSession.checkpointActive()
		await self.finishGameIfWon()
