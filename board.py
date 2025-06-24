from __future__ import annotations
from typing import Optional

from move import Move
from spot import Spot, House

from params import *

class Board:
	def __init__(self):
		self._spots = []
		for color in COLORS:
			for i in range(SPOTS_PER_REGION):
				self._spots.append(Spot(color, i))

		self._houses = []
		for color in COLORS:
			for i in range(SPOTS_PER_HOUSE):
				self._houses.append(House(color, i))

	def __str__(self) -> str:
		s = ''
		for spot in self._spots:
			if spot.isOccupied:
				s += f'Spot {str(spot)} is occupied by player {spot.occupant.name}.'
				if spot.isBlocking:
					s += ' This spot is blocked.'
				s += '\n'
		return s

	def getFirstSpot(self, color : str) -> Optional[Spot]:
		for spot in self._spots:
			if spot.color == color and spot.number == 0:
				return spot
		return None  # in case no such spot is found, but there should always be one

	def getOccupiedSpotsOnTheBoard(self, player) -> [Spot]:
		result = []
		for spot in self._spots:
			if spot.occupant == player:
				result.append(spot)
		return result

	def getOtherPiecesOnTheBoard(self, player) -> [Spot]:
		result = []
		for spot in self._spots:
			if spot.occupant != player and spot.isOccupied:
				result.append(spot)
		return result

	def getSpotFromDistance(self, originSpot : Spot, distance : int) -> Spot:
		targetIndex = self._spots.index(originSpot) + distance
		if targetIndex >= SPOTS_PER_REGION * len(COLORS):
			targetIndex -= SPOTS_PER_REGION * len(COLORS)
		if targetIndex < 0:
			targetIndex += SPOTS_PER_REGION * len(COLORS)
		return self._spots[targetIndex]

	def getHouseFromDistance(self, originSpot : Spot, distance : int, player : Player) -> House:
		print(f'Call to getHouseFromDistance with originSpot = {originSpot}, distance = {distance}, player = {player.name}')
		targetIndex = self._spots.index(originSpot) + distance
		print(f'targetIndex = {targetIndex}')
		if targetIndex >= SPOTS_PER_REGION * len(COLORS):
			targetIndex -= SPOTS_PER_REGION * len(COLORS)
			print(f'targetIndex is >= than SPOTS_PER_REGION * len(COLORS) = {SPOTS_PER_REGION * len(COLORS)}, so correcting its value to {targetIndex}')

		playerColorIndex = COLORS.index(player.color)
		firstHouseIndex = (playerColorIndex * SPOTS_PER_REGION) + 1
		print(f'firstHouseIndex = {firstHouseIndex}')
		if targetIndex in range(firstHouseIndex, firstHouseIndex + SPOTS_PER_HOUSE):
			print(f'targetIndex is in the house range so returning {self._houses[(playerColorIndex * SPOTS_PER_HOUSE) + targetIndex - firstHouseIndex]}')
			return self._houses[(playerColorIndex * SPOTS_PER_HOUSE) + targetIndex - firstHouseIndex]

		


	def isMoveValid(self, move : Move) -> bool:
		print(f'call isMoveValid with move = {move.ID}, originSpot = {move.originSpot}, targetSpot = {move.targetSpot}')
		result = True
		if move.ID == 'SWITCH' and (move.originSpot.isBlocking or move.targetSpot.isBlocking):
			# Cannot do a SWITCH move where one of the pieces is on a blocking spots
			result = False
		elif move.ID == 'OUT':
			# Cannot take a piece out if there is already a piece in the exit spot
			if move.originSpot.isBlocking:
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
		elif move.ID == 'ENTER':
			# Cannot do a ENTER move X spots if there is a house spot already taken
			if move.originSpot.isBlocking:
				return False
			return True
		print(f'returning {result}')
		return result



	def getMoveOptions(self, player : Player, card : Card) -> Optional[Move]:
		options = []
		
		# player wants to play an A : player can either get a piece out, or move a piece 11 or 1
		if card.value == 'A':
			potentialMove = Move('OUT', self.getFirstSpot(player.color), self.getFirstSpot(player.color))
			if self.isMoveValid(potentialMove):
				options.append(potentialMove)

			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 1))
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 11))
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, 1, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)
					availableHouse = self.getHouseFromDistance(piece, 11, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)


		# player wants to play a K : player can either get a piece out, or move a piece 13
		elif card.value == 'K':
			potentialMove = Move('OUT', self.getFirstSpot(player.color), self.getFirstSpot(player.color))
			if self.isMoveValid(potentialMove):
				options.append(potentialMove)

			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 13))
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, 13, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		# player wants to play a J : player can only switch two pieces together
		elif card.value == 'J':
			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			otherPiecesOnTheBoard = self.getOtherPiecesOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0 and len(otherPiecesOnTheBoard) > 0:
				# player has at least a piece on the board, and there is at least one other piece on the board belonging to another player
				for piece in occupiedSpotsOnTheBoard:
					for other_piece in otherPiecesOnTheBoard:
						potentialMove = Move('SWITCH', piece, other_piece)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		# player wants to play a 4 : player can either move 4 or -4
		elif card.value == '4':
			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 4))
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)
					potentialMove = Move('BACK', piece, self.getSpotFromDistance(piece, -4))
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, 4, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		# player wants to play a 7 : player can move exactly 7 times split among all the pieces he/she has one the board
		elif card.value == '7':
			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 7))
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, 7, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		# player is playing any other card, only possible move is to go forward
		else:
			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, card.getNumValue()))
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, card.getNumValue(), player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		return options