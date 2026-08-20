from __future__ import annotations
from typing import Optional

from move import Move
from spot import Spot, House
from cards import Card
from rules import FiveBehaviour, GameRules, MONTSURVENT_RULES

from params import *


class Board:
	def __init__(self, colors : List, rules: GameRules = MONTSURVENT_RULES):
		self._rules = rules
		self._spots = []
		self._colors = colors

		self._regionLength = rules.track_region_length

		for color in colors:
			for i in range(self._regionLength):
				self._spots.append(Spot(color, i))

		self._boardSize = len(self._spots)

		self._houses = []
		for color in colors:
			for i in range(SPOTS_PER_HOUSE):
				self._houses.append(House(color, i))

		print(f'Created the board with the following ordered colors: {colors}')

	@property
	def rules(self) -> GameRules:
		return self._rules

	@property
	def regionLength(self) -> int:
		return self._regionLength

	@property
	def boardSize(self) -> int:
		return self._boardSize

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

	def getSpot(self, color : str, number : int) -> Spot:
		if not 0 <= number < self._regionLength:
			raise ValueError(f"Position number {number} is outside a region of length {self._regionLength}")

		return self._spots[self._colors.index(color) * self._regionLength + number]

	def getSpotById(self, spotId : str) -> Spot:
		return [spot for spot in self._spots if str(spot) == spotId][0]

	def getHouse(self, color : str, number : int) -> Spot:
		return self._houses[self._colors.index(color)*SPOTS_PER_HOUSE + number]

	def getHouseById(self, houseId : str) -> Spot:
		return [house for house in self._houses if str(house) == houseId][0]

	def getFirstSpot(self, color : str) -> Optional[Spot]:
		return [spot for spot in self._spots if spot.color == color and spot.number == 0][0]

	def getHouseEntrySpot(self, color: str) -> Spot:
		if self._rules.enter_house_at_spot == self._regionLength:
			return self.getFirstSpot(color)

		return self.getSpot(self.getPreviousColor(color), self._rules.enter_house_at_spot)

	def getOccupiedSpotsOnTheBoard(self, player) -> list[Spot]:
		return [spot for spot in self._spots if not spot.occupant is None and spot.occupant.name == player]

	def getOccupiedHouses(self, player) -> list[House]:
			return [house for house in self._houses if house.isOccupied and house.occupant.name == player]

	def getOtherPiecesOnTheBoard(self, player) -> list[Spot]:
		return [spot for spot in self._spots if spot.occupant != player and spot.isOccupied]

	def getOpponentPiecesOnTheBoard(self, player) -> list[Spot]:
		return [spot for spot in self._spots if spot.isOccupied and spot.occupant.team != player.team]

	def getAllPiecesOfOtherPlayer(self, player) -> list[Spot]:
		return self.getOtherPiecesOnTheBoard(player)

	def getAllPiecesOnTheBoard(self) -> list[Spot]:
		return [{"spotIndex": str(house), "playerId": house.occupant.name} for house in self._houses if house.isOccupied] + [{"spotIndex": str(spot), "playerId": spot.occupant.name} for spot in self._spots if spot.isOccupied]

	def getSpotFromDistance(self, originSpot: Spot, distance: int) -> Spot:
		originIndex = self._spots.index(originSpot)
		targetIndex = (originIndex + distance) % self._boardSize

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
			entrySpot = self.getHouseEntrySpot(player.color)
			exitSpot = self.getFirstSpot(player.color)

			# A freshly deployed piece cannot immediately enter its houses.
			if originSpot is exitSpot and exitSpot.isFreshlyDeployed:
				return None

			# A protected entry prevents every piece from entering.
			if entrySpot.isBlocking:
				return None

			originIndex = self._spots.index(originSpot)
			entryIndex = self._spots.index(entrySpot)

			stepsToEntry = (entryIndex - originIndex) % self._boardSize

			for step in range(1, stepsToEntry + 1):
				if self.getSpotFromDistance(originSpot, step).isBlocking:
					return None

			# Reaching the entry position is still an ordinary track move.
			# House zero requires one additional forward step.
			targetHouseNumber = (distance - stepsToEntry - 1)

		if 0 <= targetHouseNumber < SPOTS_PER_HOUSE:
				return self.getHouse(player.color, targetHouseNumber)

		return None

	def getForwardMoveOptions(self, player: Player, card: Card, distances: list[int], pieceOwner: Player = None) -> list[Move]:
		pieceOwner = pieceOwner if pieceOwner is not None else player
		options = []

		boardPieces = self.getOccupiedSpotsOnTheBoard(pieceOwner.name)
		housePieces = self.getOccupiedHouses(pieceOwner.name)

		for distance in distances:
			# Pieces on the circular track can either remain on the track
			# or enter their house lane when both moves are legal.
			for piece in boardPieces:
				trackMove = Move("MOVE", piece, self.getSpotFromDistance(piece, distance), card, player, pieceOwner, distance)

				if self.isMoveValid(trackMove):
					options.append(trackMove)

				availableHouse = self.getHouseFromDistance(piece, distance, pieceOwner)

				if availableHouse is not None:
					houseMove = Move("ENTER", piece, availableHouse, card, player, pieceOwner, distance)

					if self.isMoveValid(houseMove):
						options.append(houseMove)

			# Pieces already inside houses can only move farther forward
			# through the same house lane.
			for piece in housePieces:
				availableHouse = self.getHouseFromDistance(piece, distance, pieceOwner)

				if availableHouse is not None:
					houseMove = Move("ENTER", piece, availableHouse, card, player, pieceOwner, distance)

					if self.isMoveValid(houseMove):
						options.append(houseMove)

		return options

	def getPositionSnapshot(self) -> list[tuple]:
		return [(position, position.occupant, position.isBlocking, position.isFreshlyDeployed) for position in self._spots + self._houses]


	def restorePositionSnapshot(self, snapshot: list[tuple]) -> None:
		for position, occupant, isBlocking, isFreshlyDeployed in snapshot:
			position.setEmpty()

			if occupant is not None:
				position.setOccupant(occupant, isFreshlyDeployed, isBlocking)

	def getHouseFromBackwardDistance(self, originSpot: Spot, distance: int, player: Player) -> Optional[House]:
		if distance <= 0 or isinstance(originSpot, House):
			return None

		entrySpot = self.getHouseEntrySpot(player.color)
		exitSpot = self.getFirstSpot(player.color)

		# A freshly deployed piece cannot immediately enter its houses.
		if originSpot is exitSpot and exitSpot.isFreshlyDeployed:
			return None

		originIndex = self._spots.index(originSpot)
		entryIndex = self._spots.index(entrySpot)
		stepsToEntry = (originIndex - entryIndex) % self._boardSize

		# A protected exit spot crossed on the way blocks the movement.
		for step in range(1, stepsToEntry + 1):
			if self.getSpotFromDistance(originSpot, -step).isBlocking:
				return None

		targetHouseNumber = distance - stepsToEntry - 1

		if 0 <= targetHouseNumber < len(self.getHousesByColor(player.color)):
			return self.getHouse(player.color, targetHouseNumber)

		return None

	def applySimulatedMove(self, move: Move) -> None:
		move.originSpot.setEmpty()
		move.targetSpot.setOccupant(move.pieceOwner)

	def isMoveValid(self, move : Move) -> bool:
		##debug##print(f'call isMoveValid with move = {move.ID}, originSpot = {move.originSpot}, targetSpot = {move.targetSpot}')
		result = True
		
		landingMoveTypes = ("OUT", "MOVE", "BACK", "FIVE", "HOP", "ENTER")
		isPathKickingSevenStep = move.card is not None and move.card.suit == "" and move.card.value == "1" and self._rules.seven_split_kicks_pieces_on_path

		if not self._rules.landing_on_occupied_spot_kicks_piece and move.ID in landingMoveTypes and move.targetSpot is not None and move.targetSpot.isOccupied and not isPathKickingSevenStep:
			return False

		if move.ID == 'SWITCH' and (move.originSpot.isBlocking or move.targetSpot.isBlocking):
			# Cannot do a SWITCH move where one of the pieces is on a blocking spots
			result = False
		elif move.ID == 'OUT':
			# Cannot take a piece out if there is already a piece in the exit spot
			if move.originSpot.isBlocking:
				result = False
			# Cannot take more pieces out than there are spots in the houses
			if move.pieceOwner.piecesOnTheBoard == SPOTS_PER_HOUSE:
				result = False
		elif move.ID in ["MOVE", "FIVE"]:
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

			elif target.color != move.pieceOwner.color:
				result = False

			else:
				houses = self.getHousesByColor(target.color)

				if target.isOccupied and self._rules.house_spots_are_blocking_and_protected:
					result = False

				if isinstance(origin, House):
					# A piece already inside the lane can only move forward.
					if origin.color != target.color or target.number <= origin.number:
						result = False

					elif self._rules.house_spots_are_blocking_and_protected:
						housesBetween = houses[origin.number + 1:target.number]

						if any(house.isOccupied for house in housesBetween):
							result = False

				else:
					# A protected exit position still blocks house entry.
					if self.getHouseEntrySpot(target.color).isBlocking:
						result = False

					elif self._rules.house_spots_are_blocking_and_protected:
						housesBeforeTarget = houses[:target.number]

						if any(house.isOccupied for house in housesBeforeTarget):
							result = False
		elif move.ID == "SEVEN":
			if self._rules.seven_split_kicks_pieces_on_path:
				sevenOptions = self.getSevenStepOptions(move.player, 7, move.pieceOwner)
			else:
				sevenOptions = self.getSevenAllocationOptions(move.player, 7, move.pieceOwner)

			if move.pieceOwner.piecesOnTheBoard == 0 or not sevenOptions:
				result = False

		return result

	def getMoveOptions(self, player: Player, card: Card, pieceOwner: Player = None) -> Optional[list[Move]]:
		pieceOwner = pieceOwner if pieceOwner is not None else player
		options = []

		if card.value == "A":
			exitSpot = self.getFirstSpot(pieceOwner.color)
			exitMove = Move("OUT", exitSpot, exitSpot, card, player, pieceOwner)

			if self.isMoveValid(exitMove):
				options.append(exitMove)

			options.extend(self.getForwardMoveOptions(player, card, list(self._rules.ace_values), pieceOwner))

		elif card.value == "K":
			exitSpot = self.getFirstSpot(pieceOwner.color)
			exitMove = Move("OUT", exitSpot, exitSpot, card, player, pieceOwner)

			if self.isMoveValid(exitMove):
				options.append(exitMove)

			options.extend(self.getForwardMoveOptions(player, card, [13], pieceOwner))

		elif card.value == "J":
			if self._rules.jacks_can_switch:
				ownPieces = self.getOccupiedSpotsOnTheBoard(pieceOwner.name)
				otherPieces = self.getOtherPiecesOnTheBoard(pieceOwner)

				for ownPiece in ownPieces:
					for otherPiece in otherPieces:
						switchMove = Move("SWITCH", ownPiece, otherPiece, card, player, pieceOwner)

						if self.isMoveValid(switchMove):
							options.append(switchMove)

			else:
				options.extend(self.getForwardMoveOptions(player, card, [11], pieceOwner))

		elif card.value == "4":
			# Forward four uses the ordinary forward and house rules.
			options.extend(self.getForwardMoveOptions(player, card, [4], pieceOwner))

			# Backward four applies only to pieces on the circular track.
			if self._rules.four_can_move_backward:
				for piece in self.getOccupiedSpotsOnTheBoard(pieceOwner.name):
					backwardMove = Move("BACK", piece, self.getSpotFromDistance(piece, -4), card, player, pieceOwner)

					if self.isMoveValid(backwardMove):
						options.append(backwardMove)

					if self._rules.can_enter_house_backward:
						availableHouse = self.getHouseFromBackwardDistance(piece, 4, pieceOwner)

						if availableHouse is not None:
							backwardHouseMove = Move("ENTER", piece, availableHouse, card, player, pieceOwner)

							if self.isMoveValid(backwardHouseMove):
								options.append(backwardHouseMove)

		elif card.value == "7":
			if self._rules.seven_can_split:
				sevenMove = Move("SEVEN", None, None, card, player, pieceOwner)

				if self.isMoveValid(sevenMove):
					options.append(sevenMove)

			else:
				options.extend(self.getForwardMoveOptions(player, card, [7], pieceOwner))

		elif card.value == "5":
			if self._rules.five_behaviour in (FiveBehaviour.FORCE_MOVE_OPPONENT, FiveBehaviour.BOTH):
				opponentPieces = self.getOpponentPiecesOnTheBoard(player)

				for piece in opponentPieces:
					movedPieceOwner = piece.occupant
					target = self.getSpotFromDistance(piece, 5)
					potentialMove = Move("FIVE", piece, target, card, player, movedPieceOwner)

					if self.isMoveValid(potentialMove):
						options.append(potentialMove)

			if self._rules.five_behaviour in (FiveBehaviour.NORMAL_MOVE_BY_FIVE, FiveBehaviour.BOTH):
				options.extend(self.getForwardMoveOptions(player, card, [5], pieceOwner))

		# Internal one-step card used to calculate and execute seven-split steps.
		elif card.value == "1":
			options.extend(self.getForwardMoveOptions(player, card, [1], pieceOwner))

		else:
			options.extend(self.getForwardMoveOptions(player, card, [card.numValue], pieceOwner))

		return options

	def getSevenStepOptions(self, player: Player, stepsRemaining: int, pieceOwner: Player = None) -> list[Move]:
		if stepsRemaining <= 0:
			return []

		pieceOwner = pieceOwner if pieceOwner is not None else player
		candidates = self.getForwardMoveOptions(player, Card("", "1"), [1], pieceOwner)

		if stepsRemaining == 1:
			return candidates

		viableOptions = []

		for move in candidates:
			snapshot = self.getPositionSnapshot()
			self.applySimulatedMove(move)

			if self.getSevenStepOptions(player, stepsRemaining - 1, pieceOwner):
				viableOptions.append(move)

			self.restorePositionSnapshot(snapshot)

		return viableOptions

	def getNextSevenSpot(self, originSpot: Spot, direction: int = 1) -> Spot:
		if originSpot not in self._spots or originSpot.number != 7:
			raise ValueError("A seven-hop must start on a track position numbered 7.")

		if direction not in [-1, 1]:
			raise ValueError("A seven-hop direction must be either 1 or -1.")

		return self.getSpotFromDistance(originSpot, direction * self._regionLength)

	def getSevenAllocationOptions(self, player: Player, stepsRemaining: int, pieceOwner: Player = None, movedPiecePositions: set[Spot] = None) -> list[Move]:
		if stepsRemaining <= 0:
			return []

		pieceOwner = pieceOwner if pieceOwner is not None else player
		movedPiecePositions = set() if movedPiecePositions is None else movedPiecePositions
		candidates = []

		for distance in range(1, stepsRemaining + 1):
			candidates.extend(self.getForwardMoveOptions(player, Card("", "1"), [distance], pieceOwner))

		candidates = [move for move in candidates if move.originSpot not in movedPiecePositions]
		viableOptions = []

		for move in candidates:
			if move.steps == stepsRemaining:
				viableOptions.append(move)
				continue

			snapshot = self.getPositionSnapshot()
			self.applySimulatedMove(move)

			nextMovedPiecePositions = movedPiecePositions.copy()
			nextMovedPiecePositions.add(move.targetSpot)

			if self.getSevenAllocationOptions(player, stepsRemaining - move.steps, pieceOwner, nextMovedPiecePositions):
				viableOptions.append(move)

			self.restorePositionSnapshot(snapshot)

		return viableOptions

	def getSevenHopMove(self, triggeringMove: Move) -> Optional[Move]:
		allowedMoveTypes = ["MOVE", "BACK", "FIVE"]

		if self._rules.jacks_can_switch and self._rules.jacks_can_switch_then_seven_hop:
			allowedMoveTypes.append("SWITCH")

		if triggeringMove.ID not in allowedMoveTypes:
			return None

		origin = triggeringMove.targetSpot

		if origin not in self._spots or origin.number != 7:
			return None

		direction = -1 if triggeringMove.ID == "BACK" and self._rules.seven_hopping_on_four_backward_goes_backward else 1
		target = self.getNextSevenSpot(origin, direction)

		hopMove = Move("HOP", origin, target, triggeringMove.card, triggeringMove.player, triggeringMove.pieceOwner)

		return hopMove if self.isMoveValid(hopMove) else None

	def getPositionsCrossedByMove(self, move: Move) -> list[Spot]:
		if move.steps is None or move.steps <= 1:
			return []

		if move.ID == "MOVE":
			return [self.getSpotFromDistance(move.originSpot, distance) for distance in range(1, move.steps)]

		if move.ID != "ENTER":
			return []

		if isinstance(move.originSpot, House):
			houses = self.getHousesByColor(move.pieceOwner.color)
			return houses[move.originSpot.number + 1:move.targetSpot.number]

		entrySpot = self.getHouseEntrySpot(move.pieceOwner.color)
		originIndex = self._spots.index(move.originSpot)
		entryIndex = self._spots.index(entrySpot)
		stepsToEntry = (entryIndex - originIndex) % self._boardSize

		trackPositions = [self.getSpotFromDistance(move.originSpot, distance) for distance in range(1, stepsToEntry + 1)]
		housePositions = self.getHousesByColor(move.pieceOwner.color)[:move.targetSpot.number]

		return trackPositions + housePositions