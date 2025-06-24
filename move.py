from __future__ import annotations
from typing import Optional

from params import *

class Move:
	def __init__(self, ID : int, originSpot : Spot = None, targetSpot : Spot = None):
		self._ID = ID
		self._description = MOVE_DESCRIPTION[self._ID]
		self._originSpot = originSpot
		self._targetSpot = targetSpot

	@property
	def ID(self) -> str:
		return self._ID

	@property
	def originSpot(self) -> Spot:
		return self._originSpot

	@property
	def targetSpot(self) -> Spot:
		return self._targetSpot

	def __str__(self) -> str:
		return self._description

	def __repr__(self) -> str:
		return f'REPR of Move with ID : {self._ID}, originSpot {self._originSpot}, targetSpot {self._targetSpot}'

	def updateDescription(self) -> None:
		if self._ID == 'MOVE':
			self._description = f'Move piece currently in spot {self._originSpot} to spot {self._targetSpot}'
			if self._targetSpot.isOccupied:
				self._description += f' and kick the piece of player {self._targetSpot.occupant.name} which is in the spot.'
		elif self._ID == 'BACK':
			self._description = f'Move piece currently in spot {self._originSpot} back to spot {self._targetSpot}'
			if self._targetSpot.isOccupied:
				self._description += f' and kick the piece of player {self._targetSpot.occupant} which is in the spot.'
		elif self._ID == 'ENTER':
			self._description = f'Move piece currently in spot {self._originSpot} back to house spot {self._targetSpot}'
		elif self._ID == 'SWITCH':
			self._description = f'Switch piece in spot {self._originSpot} with piece of player {self._targetSpot.occupant.name} in spot {self._targetSpot}'