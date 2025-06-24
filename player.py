from __future__ import annotations
from typing import Optional

from params import *

class Player:
	def __init__(self, name : str, team : str, color : str):
		self._name = str(name)
		self._team = str(team)
		self._color = str(color)
		self._hand = None
		self._active = False
		self._isDealer = False

	def __str__(self) -> str:
		s = f'{self._name} in team {self._team} playing {self._color}'
		if self._hand:
			s+= f' holding the following cards: {self._hand.allCardsString()}'
		return s

	@property
	def name(self) -> str:
		return self._name
	
	@property
	def team(self) -> str:
		return self._team

	@property
	def color(self) -> str:
		return self._color

	@property
	def hand(self) -> Hand:
		return self._hand

	def setHand(self, hand : Hand):
		self._hand = hand

	def setDealer(self):
		self._isDealer = True

	def getCardChoiceFromPlayer(self) -> Card:
		choice = self._hand.getCard(input('What card do you want to play?\t'))
		while choice is None:
			print(f'Please input a number between 0 and {self._hand.size - 1} to select an available card from your hand.')
			choice = self._hand.getCard(input('What card do you want to play?\t'))
		return choice


	def getMoveChoiceFromPlayer(self, options : [Move]) -> Move:
		for move in options:
			move.updateDescription()

		print([str(option) for option in options])

		choice = input('What move do you want to play?\t')
		while choice not in [str(i) for i in range(len(options))]:
			print(f'Please input a number between 0 and {len(options) - 1} to select an available move based on the card you selected.')
			choice = input('What move do you want to play?\t')
		return options[int(choice)]

	def discard(self, card) -> None:
		self._hand.discardFromHand(card)