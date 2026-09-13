from __future__ import annotations

import random

from toc.model.hand import Hand
from toc.model.params import *


class Deck:
	def __init__(self, jokerCount: int = 0) -> None:
		if type(jokerCount) is not int or not 0 <= jokerCount <= len(JOKER_COLORS):
			raise ValueError("Invalid Joker count")

		standardCards = [Card(suit, value, self) for value in VALUES for suit in SUITS]
		jokers = [Card(color, JOKER_VALUE, self) for color in JOKER_COLORS[:jokerCount]]

		self._cards = standardCards + jokers
		self._expectedCardCount = len(self._cards)
		random.shuffle(self._cards)
		self._discardPile = []
		self._player = None

	@property
	def cards(self) -> list[Card]:
		return self._cards

	@property
	def size(self) -> int:
		return len(self._cards)

	@property
	def expectedCardCount(self) -> int:
		return self._expectedCardCount

	@property
	def discardPile(self) -> list[Card]:
		return self._discardPile

	@classmethod
	def fromPiles(cls, drawPile: list[Card], discardPile: list[Card], expectedCardCount: int = 52) -> "Deck":
		if type(drawPile) is not list or type(discardPile) is not list:
			raise ValueError("Deck piles must be lists")

		if not all(isinstance(card, Card) for card in drawPile + discardPile):
			raise ValueError("Deck piles contain an invalid card")

		if type(expectedCardCount) is not int or expectedCardCount not in (52, 54):
			raise ValueError("Invalid expected deck size")

		if len(drawPile) + len(discardPile) > expectedCardCount:
			raise ValueError("Deck piles contain too many cards")

		deck = cls.__new__(cls)
		deck._cards = list(drawPile)
		deck._discardPile = list(discardPile)
		deck._expectedCardCount = expectedCardCount
		deck._player = None

		for card in deck._cards + deck._discardPile:
			card._deck = deck

		return deck

	def drawCard(self) -> Card:
		if not self._cards:
			raise RuntimeError("Cannot draw a card from an empty deck")

		return self._cards.pop(0)

	def discardCard(self, card: Card) -> None:
		self._discardPile.append(card)

	def discardCards(self, hand: Hand) -> None:
		self._discardPile.extend(hand.cards)

	def recycleDiscardPile(self, shuffle: bool = False) -> None:
		if self._cards:
			raise RuntimeError("Cannot recycle the discard pile while cards remain in the deck")

		if len(self._discardPile) != self._expectedCardCount:
			raise RuntimeError(f"Cannot recycle an incomplete discard pile containing {len(self._discardPile)} cards")

		self._cards = self._discardPile
		self._discardPile = []

		if shuffle:
			random.shuffle(self._cards)


class Card:
	def __init__(self, suit: str, value: str, deck: Deck | None = None) -> None:
		self._suit = suit
		self._value = value
		self._deck = deck

	def __str__(self) -> str:
		return f'{self._suit}{self._value}'

	def __eq__(self, other: object) -> bool:
		if isinstance(other, Card):
			return self.suit == other.suit and self.value == other.value
		return False

	def __hash__(self) -> int:
		return hash((self.suit, self.value))

	@property
	def value(self) -> str:
		return self._value

	@property
	def suit(self) -> str:
		return self._suit

	@property
	def json(self) -> dict[str, str]:
		return {"suit": self._suit, "value": self._value}

	@property
	def numValue(self) -> int:
		if self._value in [str(i) for i in range(1, 10)]:
			return int(self._value)
		elif self._value == 'T':
			return 10
		elif self._value == 'J':
			return 11
		elif self._value == 'Q':
			return 12
		elif self._value == 'K':
			return 13
		elif self._value == 'A':
			return 11
		elif self._value == JOKER_VALUE:
			return 18
		else:
			return 0