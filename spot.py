from __future__ import annotations
from typing import Optional

from player import Player


class Spot:
	def __init__(self, color : str, number : int):
		self._color = color
		self._number = number
		self._isOccupied = False
		self._isBlocking = False
		self._occupant = None

	def __str__(self) -> str:
		return self._color+'-'+str(self._number)

	@property
	def color(self) -> str:
		return self._color

	@property
	def number(self) -> int:
		return self._number

	@property
	def isOccupied(self) -> bool:
		return self._isOccupied

	@property
	def isBlocking(self) -> bool:
		return self._isBlocking

	@property
	def occupant(self) -> Player:
		return self._occupant

	def setOccupant(self, player : Player, isOwnPlayerTakingAPieceOut : bool = False) -> Optional[Player]:
		# The 'result' variable is returned with the previous occupant of the spot, if there is one. This is used by the game.py logic to decrease the counter keeping track of how many pieces any given player has on the board. 
		result = None
		if self._isOccupied:
			result = self._occupant
		
		self._occupant = player
		self._isOccupied = True

		if isOwnPlayerTakingAPieceOut:
			self._isBlocking = True

		return result

	def setEmpty(self):
		self._occupant = None
		self._isOccupied = False
		self._isBlocking = False

class House(Spot):
	def __str__(self) -> str:
		return 'house-'+self._color+'-'+str(self._number)