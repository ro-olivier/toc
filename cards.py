from __future__ import annotations

from hand import Hand
from params import *

import random


class Deck:
	def __init__(self):
		self._cards = [Card(suit, value, self) for value in VALUES for suit in SUITS]
		random.shuffle(self._cards)

		self._discardPile = []
		self._player = None

	def drawHand(self, number_of_cards : int, player : Player) -> Hand:
		if not number_of_cards in [4, 5]:
			raise Exception(f'A hand with {number_of_cards} was requested: that\'s not possible...')
		else:
			temp = []
			for n in range(number_of_cards):
				picked_card = random.choice(self._cards)
				remaining_cards = [card for card in self._cards if card != picked_card]
				self._cards = remaining_cards
				temp.append(picked_card)
			self._player = player
			return Hand(temp, player)

	@property
	def discardPile(self) -> list[Card]:
		return self._discardPile

	def reset(self, players) -> None:
		player_index = 0
		temp_hands = []
		for card in self._discardPile:
			temp_hands.append(card)
			player_index += 1
			if player_index == NUMBER_OF_PLAYERS:
				player_index = 0

		for index, player in enumerate(players):
			player.setHand(temp_hands[index])


class Card:
	def __init__(self, suit : str, value : str, deck : Deck = None):
		self._suit = suit
		self._value = value
		self._deck = deck

	def __str__(self) -> str:
		return f'{self._suit}{self._value}'

	@property
	def value(self) -> str:
		return self._value

	@property
	def json(self) -> dict:
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
		else:
			return 0

	def discard(self) -> None:
		self._deck.discardPile.append(self)