from __future__ import annotations
from typing import Optional

from params import *

class Hand:
	def __init__(self, cards : [Cards], player : Player):
		if len(cards) in [4, 5]:
			self._player = player
			self._cards = cards
		else:
			raise Exception(f'Cannot create a hand of less than 4 cards or more than 5 cards...')

	def __str__(self):
		if len(self._cards) == 0:
			return f'{self._player.name}\'s hand is empty'
		else:
			s = f'{self._player.name}\'s hand is composed of {self._remainingCards} cards: '
			for card in self._cards[:-1]:
				s += str(card) + ', '
			s += str(self._cards[-1])
			return s

	def allCardsString(self) -> str:
		if len(self._cards) == 0:
			return ''
		else:
			s = ''
		for card in self._cards[:-1]:
			s += str(card) + ', '
		s += str(self._cards[-1])
		return s

	@property
	def size(self) -> int:
		return len(self._cards)

	def getCard(self, index : str) -> Card:
		try:
			return self._cards[int(index)]
		except:
			return None

	def hasNoExitCard(self) -> bool:
		if any([card.value in ['A', 'K'] for card in self._cards]):
			return False
		else:
			return True

	def fold(self) -> None:
		for index, card in enumerate(self._cards):
			card.discard()
		self._cards = []

	def discardFromHand(self, card) -> None:
		del self._cards[self._cards.index(card)]