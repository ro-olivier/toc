from __future__ import annotations

from toc.model.player import Player


class Spot:
	def __init__(self, color: str, number: int) -> None:
		self._color = color
		self._number = number
		self._isOccupied = False
		self._isBlocking = False
		self._isFreshlyDeployed = False
		self._occupant = None

	def __str__(self) -> str:
		return 'spot-'+self._color+'-'+str(self._number)

	def __eq__(self, other: object) -> bool:
		if isinstance(other, Spot):
			return str(self) == str(other)
		return False

	def __hash__(self) -> int:
		return hash(str(self))

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
	def isFreshlyDeployed(self) -> bool:
		return self._isFreshlyDeployed

	@property
	def occupant(self) -> Player | None:
		return self._occupant

	def setOccupant(self, player: Player, isOwnPlayerTakingAPieceOut: bool = False, isBlocking: bool | None = None) -> Player | None:
		# The 'result' variable is returned with the previous occupant of the spot, if there is one. This is used by the game.py logic to decrease the counter keeping track of how many pieces any given player has on the board. 
		result = None
		if self._isOccupied:
			result = self._occupant
		
		self._occupant = player
		self._isOccupied = True

		self._isFreshlyDeployed = isOwnPlayerTakingAPieceOut
		self._isBlocking = isOwnPlayerTakingAPieceOut if isBlocking is None else isBlocking

		return result

	def setEmpty(self) -> None:
		self._occupant = None
		self._isOccupied = False
		self._isBlocking = False
		self._isFreshlyDeployed = False


class House(Spot):
	def __str__(self) -> str:
		return 'house-'+self._color+'-'+str(self._number)