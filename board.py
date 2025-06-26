from __future__ import annotations
from typing import Optional
import copy

from move import Move
from spot import Spot, House

from params import *

class Board:
	def __init__(self):
		self._savedState = None
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
		for house in self._houses:
			if house.isOccupied:
				s += f'House {str(house)} is occupied by player {house.occupant.name}.\n'
		return s

	def getHousesByColor(self, color : str) -> list[House]:
		colorIndex = COLORS.index(color)
		return self._houses[colorIndex * SPOTS_PER_HOUSE: (colorIndex + 1) * SPOTS_PER_HOUSE]

	def areAllHouseFilled(self, color : str) -> bool:
		return all([house.isOccupied for house in self.getHousesByColor(color)])

	def getPreviousColor(self, color : str) -> str:
		colorIndex = COLORS.index(color)
		if colorIndex == 0:
			return COLORS[-1]
		else:
			return COLORS[colorIndex - 1]

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
		return self._spots[COLORS.index(color)*SPOTS_PER_REGION + number]

	def getHouse(self, color : str, number : int) -> Spot:
		return self._houses[COLORS.index(color)*SPOTS_PER_HOUSE + number]

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
				if spot.occupant.name == player.name:
					result.append(spot)
		##debug##print(f'returning : {result}')
		return result

	def getOtherPiecesOnTheBoard(self, player) -> list[Spot]:
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

	def getHouseFromDistance(self, originSpot : Spot, distance : int, player : Player) -> Optional[House]:
		##TODO##TOCHECH##

		##debug##print(f'Call to getHouseFromDistance with originSpot = {originSpot}, distance = {distance}, player = {player.name}')
		
		if originSpot.color != self.getPreviousColor(player.color) or (originSpot.color == player.color and originSpot.number != 0 and originSpot.isBlocking):
			# houses are only reachable from spots just before the player's own color, or from the player own color-0 spot (unless it just exited and thus is blocking).
			##debug##print('Returning empty array because current spot cannot reach any house')
			return None

		targetIndex = self._spots.index(originSpot) + distance
		##debug##print(f'targetIndex = {targetIndex}')
		if targetIndex >= SPOTS_PER_REGION * len(COLORS):
			targetIndex -= SPOTS_PER_REGION * len(COLORS)
			##debug##print(f'targetIndex is >= than SPOTS_PER_REGION * len(COLORS) = {SPOTS_PER_REGION * len(COLORS)}, so correcting its value to {targetIndex}')

		playerColorIndex = COLORS.index(player.color)
		firstHouseIndex = (playerColorIndex * SPOTS_PER_REGION)
		##debug##print(f'firstHouseIndex = {firstHouseIndex}')
		if targetIndex in range(firstHouseIndex, firstHouseIndex + SPOTS_PER_HOUSE):
			##debug##print(f'targetIndex is in the house range so returning {self._houses[(playerColorIndex * SPOTS_PER_HOUSE) + targetIndex - firstHouseIndex  - 1]}')
			return self._houses[(playerColorIndex * SPOTS_PER_HOUSE) + targetIndex - firstHouseIndex - 1]
		return None

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
		elif move.ID == 'ENTER':
			# Cannot do a ENTER move X spots if there is a house spot already taken before...
			# also if the player is coming from a spot before the exit point then it's OK to enter at any of the 4 houses as long as the previous houses (before the targetted house) are not already occupied
			# if the player is coming from another house before the target house, it's actually the same logic, the houses in between the origin house and the targethouse cannot be occupied
			houseColor = move.targetSpot.color
			##debug##print(f'isinstance(move.originSpot, Spot) = {isinstance(move.originSpot, Spot)} and self.getFirstSpot(houseColor).isBlocking {self.getFirstSpot(houseColor).isBlocking}')
			if isinstance(move.originSpot, Spot) and self.getFirstSpot(houseColor).isBlocking:
				result = False
			else:
				housesBeforeTarget = []
				for house in self.getHousesByColor(houseColor):
					if house.number < move.targetSpot.number:
						housesBeforeTarget.append(house) 
				##debug##print(housesBeforeTarget)
				if any(house.isOccupied for house in housesBeforeTarget):
					##debug##print('a house is blocking the way!')
					##debug##print([house.isOccupied for house in housesBeforeTarget])
					result = False
		elif move.ID == 'SEVEN':
			# Cannot do a SEVEN move if there is not at least one piece on the board
			# and even then it might not be possible !! ##TODO##
			if move.player.piecesOnTheBoard == 0:
				result = False
		##debug##		print(f'returning {result}')
		return result



	def getMoveOptions(self, player : Player, card : Card) -> Optional[list[Move]]:
		options = []
		
		# player wants to play an A : player can either get a piece out, or move a piece 11 or 1
		if card.value == 'A':
			potentialMove = Move('OUT', self.getFirstSpot(player.color), self.getFirstSpot(player.color), card, player)
			if self.isMoveValid(potentialMove):
				options.append(potentialMove)

			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 1), card, player)
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 11), card, player)
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, 1, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse, card, player)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)
					availableHouse = self.getHouseFromDistance(piece, 11, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse, card, player)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)


		# player wants to play a K : player can either get a piece out, or move a piece 13
		elif card.value == 'K':
			potentialMove = Move('OUT', self.getFirstSpot(player.color), self.getFirstSpot(player.color), card, player)
			if self.isMoveValid(potentialMove):
				options.append(potentialMove)

			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 13), card, player)
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, 13, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse, card, player)
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
						potentialMove = Move('SWITCH', piece, other_piece, card, player)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		# player wants to play a 4 : player can either move 4 or -4
		elif card.value == '4':
			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 4), card, player)
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)
					potentialMove = Move('BACK', piece, self.getSpotFromDistance(piece, -4), card, player)
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, 4, player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse, card, player)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		# player wants to play a 7 : player can move exactly 7 times split among all the pieces he/she has one the board
		elif card.value == '7':
			potentialMove = Move('SEVEN', None, None, card, player)
			if self.isMoveValid(potentialMove):
				options.append(potentialMove)

		#special card which cannot be played by a player but is used by the Player.getSevenMoveFromPlayer() method to get options for "one-step" moves during a seven split.
		elif card.value == '1':
			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			##debug##print(f'in call getMoveOptions, when asking move for a 1 (in seven-split) : occupiedSpotsOnTheBoard = {occupiedSpotsOnTheBoard}')
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, 1), card, player)
					if self.isMoveValid(potentialMove):
						##debug##print('found a valid MOVE move, appending...')
						options.append(potentialMove)
					availableHouse = self.getHouseFromDistance(piece, 1, player)
					##debug##print(f'found the following availableHouses : {availableHouse}')
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse, card, player)
						##debug##print(f'evaluation the potentialMove : {potentialMove}')
						if self.isMoveValid(potentialMove):
							##debug##print('found a valid ENTER move, appending...')
							options.append(potentialMove)


		# player is playing any other card, only possible move is to go forward
		else:
			occupiedSpotsOnTheBoard = self.getOccupiedSpotsOnTheBoard(player)
			if len(occupiedSpotsOnTheBoard) > 0:
				# player has at least a piece on the board, may be able to move them
				for piece in occupiedSpotsOnTheBoard:
					potentialMove = Move('MOVE', piece, self.getSpotFromDistance(piece, card.getNumValue()), card, player)
					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

					availableHouse = self.getHouseFromDistance(piece, card.getNumValue(), player)
					if not availableHouse is None:
						potentialMove = Move('ENTER', piece, availableHouse, card, player)
						if self.isMoveValid(potentialMove):
							options.append(potentialMove)

		return options