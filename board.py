from __future__ import annotations
from typing import Optional
import copy

from move import Move
from spot import Spot, House

from params import *


class Board:
	def __init__(self, colors : List):
		self._savedState = None
		self._spots = []
		self._colors = colors
		for color in colors:
			for i in range(SPOTS_PER_REGION):
				self._spots.append(Spot(color, i))

		self._houses = []
		for color in colors:
			for i in range(SPOTS_PER_HOUSE):
				self._houses.append(House(color, i))

		print(f'Created the board with the following ordered colors: {colors}')

	def __str__(self) -> str:
		s = ''
		for spot in self._spots:
			if spot.isOccupied:
				s += f'Spot {str(spot)} is occupied by player {spot.occupant.name}.'
				if spot.isBlocking:
					s += ' This spot is blocked.'
				s += '\n'
		for house in self._houses:
			if house.isOccupied:
				s += f'House {str(house)} is occupied by player {house.occupant.name}.\n'
		return s

	def getHousesByColor(self, color : str) -> list[House]:
		colorIndex = self._colors.index(color)
		return self._houses[colorIndex * SPOTS_PER_HOUSE: (colorIndex + 1) * SPOTS_PER_HOUSE]

	def areAllHouseFilled(self, color : str) -> bool:
		return all([house.isOccupied for house in self.getHousesByColor(color)])

	def getPreviousColor(self, color : str) -> str:
		colorIndex = self._colors.index(color)
		if colorIndex == 0:
			return self._colors[-1]
		else:
			return self._colors[colorIndex - 1]

	def saveState(self) -> None:
		# This method used by the Player.getSevenMoveFromPlayer() to store the state of the board while the player is doing the "seven split".
		# This way, the seven split can be done while giving the player a view of what is done step by step, while giving the player the option
		# to cancel and choose another card to play, or to play the seven split a different way.
		self._savedState = {'Spots': copy.deepcopy(self._spots), 'Houses': copy.deepcopy(self._houses)}

	def restoreState(self) -> None:
		# See method above.
		##debug##print(f'Call to restoreState with self.saveState Spots = {[str(spot) + ' - Occupied ? ' + str(spot.isOccupied) + ' by ' + str(spot.occupant.name) for spot in self._savedState['Spots']]} and self.saveState Houses = {[str(house) + ' - Occupied ? ' + str(house.isOccupied) + ' by ' + str(house.occupant.name) for house in self._savedState['Houses']]}')
		self._spots = self._savedState['Spots']
		self._houses = self._savedState['Houses']

	def getSpot(self, color : str, number : int) -> Spot:
		return self._spots[self._colors.index(color)*SPOTS_PER_REGION + number]

	def getSpotById(self, spotId : str) -> Spot:
		res = [spot for spot in self._spots if str(spot) == spotId]
		spot = res[0]
		print(f'[getSpotById] called with spotId = {spotId}, result is {id(spot)} (len(res) was {len(res)})')
		return spot

	def getHouse(self, color : str, number : int) -> Spot:
		return self._houses[self._colors.index(color)*SPOTS_PER_HOUSE + number]

	def getHouseById(self, houseId : str) -> Spot:
		house = [house for house in self._houses if str(house) == houseId][0]
		return house

	def getFirstSpot(self, color : str) -> Optional[Spot]:
		for spot in self._spots:
			if spot.color == color and spot.number == 0:
				return spot
		return None  # in case no such spot is found, but there should always be one

	def getOccupiedSpotsOnTheBoard(self, player) -> list[Spot]:
		result = []
		##debug##print(f'Call to getOccupiedSpotsOnTheBoard with requested with current self._spots = {[str(spot) + ' - Occupied ? ' + str(spot.isOccupied) + ' by ' + str(spot.occupant) for spot in self._spots]}')
		for spot in self._spots:
			if not spot.occupant is None:
				if spot.occupant.name == player:
					result.append(spot)
		##debug##print(f'returning : {result}')
		return result

	def getOccupiedHouses(self, player) -> list[House]:
			return [
				house
				for house in self._houses
				if house.isOccupied and house.occupant.name == player
		]

	def getOtherPiecesOnTheBoard(self, player) -> list[Spot]:
		result = []
		for spot in self._spots:
			if spot.occupant != player and spot.isOccupied:
				result.append(spot)
		return result

	def getAllPiecesOfOtherPlayer(self, player) -> list[Spot]:
		return getOtherPiecesOnTheBoard(player)

	def getAllPiecesOnTheBoard(self) -> list[Spot]:
		return [{"spotIndex": str(house), "playerId": house.occupant.name} for house in self._houses if house.isOccupied] + [{"spotIndex": str(spot), "playerId": spot.occupant.name} for spot in self._spots if spot.isOccupied]

	def getSpotFromDistance(self, originSpot: Spot, distance: int) -> Spot:
		boardSize = len(self._spots)
		originIndex = self._spots.index(originSpot)
		targetIndex = (originIndex + distance) % boardSize

		return self._spots[targetIndex]


	def getHouseFromDistance(self, originSpot: Spot, distance: int, player: Player) -> Optional[House]:
		if distance <= 0:
			return None

		# A piece already inside its house lane can only continue forward
		# within that same lane.
		if isinstance(originSpot, House):
			if originSpot.color != player.color:
				return None

			targetHouseNumber = originSpot.number + distance

		else:
			entrySpot = self.getFirstSpot(player.color)

			# A freshly deployed piece cannot immediately enter its houses.
			# A protected entry also prevents another piece from entering.
			if entrySpot.isBlocking:
					return None

			boardSize = len(self._spots)
			originIndex = self._spots.index(originSpot)
			entryIndex = self._spots.index(entrySpot)

			stepsToEntry = (entryIndex - originIndex) % boardSize

			# Reaching the entry position is still an ordinary track move.
			# House zero requires one additional forward step.
			targetHouseNumber = (distance - stepsToEntry - 1)

		if 0 <= targetHouseNumber < SPOTS_PER_HOUSE:
				return self.getHouse(player.color, targetHouseNumber)

		return None

	def getForwardMoveOptions(self, player: Player, card: Card, distances: list[int]) -> list[Move]:
		options = []

		boardPieces = self.getOccupiedSpotsOnTheBoard(player.name)
		housePieces = self.getOccupiedHouses(player.name)

		for distance in distances:
			# Pieces on the circular track can either remain on the track
			# or enter their house lane when both moves are legal.
			for piece in boardPieces:
				trackMove = Move(
					"MOVE",
					piece,
					self.getSpotFromDistance(
						piece,
						distance,
					),
					card,
					player,
				)

				if self.isMoveValid(trackMove):
					options.append(trackMove)

				availableHouse = self.getHouseFromDistance(
					piece,
					distance,
					player,
				)

				if availableHouse is not None:
					houseMove = Move(
						"ENTER",
						piece,
						availableHouse,
						card,
						player,
					)

					if self.isMoveValid(houseMove):
						options.append(houseMove)

			# Pieces already inside houses can only move farther forward
			# through the same house lane.
			for piece in housePieces:
				availableHouse = self.getHouseFromDistance(
					piece,
					distance,
					player,
				)

				if availableHouse is not None:
					houseMove = Move(
						"ENTER",
						piece,
						availableHouse,
						card,
						player,
					)

					if self.isMoveValid(houseMove):
						options.append(houseMove)

		return options

	def isMoveValid(self, move : Move) -> bool:
		##debug##print(f'call isMoveValid with move = {move.ID}, originSpot = {move.originSpot}, targetSpot = {move.targetSpot}')
		result = True
		if move.ID == 'SWITCH' and (move.originSpot.isBlocking or move.targetSpot.isBlocking):
			# Cannot do a SWITCH move where one of the pieces is on a blocking spots
			result = False
		elif move.ID == 'OUT':
			# Cannot take a piece out if there is already a piece in the exit spot
			if move.originSpot.isBlocking:
				result = False
			# Cannot take more pieces out than there are spots in the houses
			if move.player.piecesOnTheBoard == SPOTS_PER_HOUSE:
				result = False
		elif move.ID == 'MOVE':
			# Cannot do a MOVE move up X spots if there is a blocking spot less or equal to X spots ahead
			i = 0
			spotAhead = self.getSpotFromDistance(move.originSpot, i + 1)
			while spotAhead != move.targetSpot:
				if spotAhead.isBlocking:
					result = False
				i += 1
				spotAhead = self.getSpotFromDistance(move.originSpot, i + 1)
			if move.targetSpot.isBlocking:
				result = False
		elif move.ID == 'BACK':
			# Cannot do a BACK move back 4 spots if there is a blocking spot less or equal to 4 spots behind
			i = 0
			spotBack = self.getSpotFromDistance(move.originSpot, i - 1)
			while spotBack != move.targetSpot:
				if spotBack.isBlocking:
					result = False
				i -= 1
				spotBack = self.getSpotFromDistance(move.originSpot, i - 1)
			if move.targetSpot.isBlocking:
				result = False
		elif move.ID == "ENTER":
			target = move.targetSpot
			origin = move.originSpot

			if not isinstance(target, House):
				result = False

			elif target.color != move.player.color:
				result = False

			elif target.isOccupied:
				# House pieces cannot be kicked or stacked.
				result = False

			else:
				houses = self.getHousesByColor(target.color)

				if isinstance(origin, House):
					# A piece already inside the lane can only move forward.
					if (origin.color != target.color or target.number <= origin.number):
						result = False

					else:
						housesBetween = houses[origin.number + 1:target.number]

						if any(house.isOccupied for house in housesBetween):
							result = False

				else:
					# A protected entry position blocks house entry.
					if self.getFirstSpot(target.color).isBlocking:
						result = False

					else:
						housesBeforeTarget = houses[:target.number]

						if any(house.isOccupied for house in housesBeforeTarget):
							result = False
		elif move.ID == 'SEVEN':
			# Cannot do a SEVEN move if there is not at least one piece on the board
			# and even then it might not be possible !! ##TODO##
			if move.player.piecesOnTheBoard == 0:
				result = False
		##debug##		print(f'returning {result}')
		return result

	def getMoveOptions(self, player: Player, card: Card) -> Optional[list[Move]]:
		options = []

		if card.value == "A":
			exitSpot = self.getFirstSpot(player.color)

			exitMove = Move(
				"OUT",
				exitSpot,
				exitSpot,
				card,
				player,
			)

			if self.isMoveValid(exitMove):
				options.append(exitMove)

			options.extend(
				self.getForwardMoveOptions(
					player,
					card,
					[1, 11],
				)
			)

		elif card.value == "K":
			exitSpot = self.getFirstSpot(player.color)

			exitMove = Move(
				"OUT",
				exitSpot,
				exitSpot,
				card,
				player,
			)

			if self.isMoveValid(exitMove):
				options.append(exitMove)

			options.extend(
				self.getForwardMoveOptions(
					player,
					card,
					[13],
				)
			)

		elif card.value == "J":
			ownPieces = self.getOccupiedSpotsOnTheBoard(
				player.name
			)
			otherPieces = self.getOtherPiecesOnTheBoard(
				player
			)

			for ownPiece in ownPieces:
				for otherPiece in otherPieces:
					switchMove = Move(
						"SWITCH",
						ownPiece,
						otherPiece,
						card,
						player,
					)

					if self.isMoveValid(switchMove):
						options.append(switchMove)

		elif card.value == "4":
			# Forward four uses the ordinary forward and house rules.
			options.extend(
				self.getForwardMoveOptions(
					player,
					card,
					[4],
				)
			)

			# Backward four applies only to pieces on the circular track.
			for piece in self.getOccupiedSpotsOnTheBoard(
				player.name
			):
				backwardMove = Move(
					"BACK",
					piece,
					self.getSpotFromDistance(
						piece,
						-4,
					),
					card,
					player,
				)

				if self.isMoveValid(backwardMove):
					options.append(backwardMove)

		elif card.value == "7":
			sevenMove = Move(
				"SEVEN",
				None,
				None,
				card,
				player,
			)

			if self.isMoveValid(sevenMove):
				options.append(sevenMove)

		elif card.value == "1":
			# Internal one-step move used while constructing a seven split.
			options.extend(
				self.getForwardMoveOptions(
					player,
					card,
					[1],
				)
			)

		else:
			options.extend(
				self.getForwardMoveOptions(
					player,
					card,
					[card.numValue],
				)
			)

		return options
