from __future__ import annotations


class Hand:
	def __init__(self, player : Player, cards : list[Card] = None):
		self._player = player
		self._cards = cards
		if cards:
			self._remainingCards = len(self._cards)

	def __str__(self) -> str:
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
		if self._cards:
			return len(self._cards)
		else:
			return 0

	@property
	def cards(self) -> list[Card]:
		return self._cards

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
		self._cards = []

	def discardFromHand(self, card) -> None:
		del self._cards[self._cards.index(card)]

	def addToHand(self, card) -> None:
		self._cards.append(card)

	def getAllPossibleMoves(self, board : Board) -> list[Move]:
		allPossibleMoveOptions = []
		for card in self._cards:
			optionsFromThisCard = board.getMoveOptions(self._player, card)
			for option in optionsFromThisCard:
				allPossibleMoveOptions.append(option)
		return allPossibleMoveOptions


