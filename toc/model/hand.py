from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from toc.model.board import Board
	from toc.model.cards import Card
	from toc.model.move import Move
	from toc.model.player import Player


class Hand:
	def __init__(self, player: Player, cards: list[Card] | None = None) -> None:
		self._player = player
		self._cards = list(cards) if cards is not None else []

	def __str__(self) -> str:
		if len(self._cards) == 0:
			return f'{self._player.name}\'s hand is empty'
		else:
			s = f'{self._player.name}\'s hand is composed of {len(self._cards)} cards: '
			for card in self._cards[:-1]:
				s += str(card) + ', '
			s += str(self._cards[-1])
			return s

	@property
	def size(self) -> int:
		if self._cards:
			return len(self._cards)
		else:
			return 0

	@property
	def cards(self) -> list[Card]:
		return self._cards

	def fold(self) -> None:
		self._cards = []

	def discardFromHand(self, card: Card) -> None:
		del self._cards[self._cards.index(card)]

	def addToHand(self, card: Card) -> None: 
		self._cards.append(card)

	def getAllPossibleMoves(self, board: Board, pieceOwner: Player | None = None) -> list[Move]:
		allPossibleMoveOptions = []

		for card in self._cards:
			optionsFromThisCard = board.getMoveOptions(self._player, card, pieceOwner)

			for option in optionsFromThisCard:
				allPossibleMoveOptions.append(option)

		return allPossibleMoveOptions

