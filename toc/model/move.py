from __future__ import annotations

from toc.model.cards import Card
from toc.model.player import Player

from toc.model.params import *


class Move:
	def __init__(self, ID : str, originSpot : Spot = None, targetSpot : Spot = None, card : Card = None, player : Player = None, pieceOwner: Player = None, steps: int = None):
		self._ID = ID
		self._description = MOVE_DESCRIPTION[self._ID]
		self._originSpot = originSpot
		self._targetSpot = targetSpot
		self._card = card
		self._player = player
		self._pieceOwner = pieceOwner if pieceOwner is not None else player
		self._steps = steps

	@property
	def ID(self) -> str:
		return self._ID

	@property
	def originSpot(self) -> Spot:
		return self._originSpot

	@property
	def targetSpot(self) -> Spot:
		return self._targetSpot

	@property
	def card(self) -> Card:
		return self._card

	@property
	def player(self) -> Player:
		return self._player

	@property
	def pieceOwner(self) -> Player:
		return self._pieceOwner

	@property
	def steps(self) -> int:
		return self._steps

	def __str__(self) -> str:
		return self._description

	def __repr__(self) -> str:
		return f'Move(ID = {self._ID}, originSpot = {self._originSpot}, targetSpot = {self._targetSpot})'

	def updateDescription(self) -> None:
		if self._ID == 'OUT':
			self._description = f'Play {self._card} to take a piece out and place it in {self._originSpot}.'
		elif self._ID == 'MOVE':
			self._description = f'Play {self._card} to move piece currently in spot {self._originSpot} to spot {self._targetSpot}'
			if self._targetSpot.isOccupied:
				self._description += f' and kick the piece of player {self._targetSpot.occupant.name} which is in the spot.'
			else:
				self._description += '.'
		elif self._ID == 'BACK':
			self._description = f'Play {self._card} to move piece currently in spot {self._originSpot} back to spot {self._targetSpot}'
			if self._targetSpot.isOccupied:
				self._description += f' and kick the piece of player {self._targetSpot.occupant} which is in the spot.'
			else:
				self._description += '.'
		elif self._ID == 'ENTER':
			self._description = f'Play {self._card} to move piece currently in spot {self._originSpot} back to house spot {self._targetSpot}.'
		elif self._ID == 'SWITCH':
			self._description = f'Play {self._card} to switch piece in spot {self._originSpot} with piece of player {self._targetSpot.occupant.name} in spot {self._targetSpot}.'
		elif self._ID == 'SEVEN':
			self._description = f'Play {self._card} to do a "seven split" : move any of your pieces as you wish a total of 7 times, kicking any piece you meet as you go.'
		elif self._ID == 'FIVE':
			self._description = f'Play {self._card} to do force an opponent to move 5 spots forward.'
		elif self._ID == 'HOP':
			self._description = f'Seven-hop the piece from {self._originSpot} to {self._targetSpot}.'
