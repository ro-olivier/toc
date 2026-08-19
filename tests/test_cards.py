from cards import Card, Deck


def test_deck_contains_52_cards():
    deck = Deck()

    assert len(deck._cards) == 52


def test_deck_contains_no_duplicate_cards():
    deck = Deck()

    assert len(set(deck._cards)) == 52


def test_card_numeric_values():
    assert Card("♥️", "2").numValue == 2
    assert Card("♥️", "T").numValue == 10
    assert Card("♥️", "J").numValue == 11
    assert Card("♥️", "Q").numValue == 12
    assert Card("♥️", "K").numValue == 13
    assert Card("♥️", "A").numValue == 11

def test_recycled_discard_pile_preserves_card_order():
    deck = Deck()
    drawnCards = [deck.drawCard() for _ in range(52)]

    for card in drawnCards:
        deck.discardCard(card)

    deck.recycleDiscardPile()

    assert deck.cards == drawnCards
    assert deck.discardPile == []
    assert deck.size == 52

def test_drawing_all_cards_empties_deck():
    deck = Deck()

    for _ in range(52):
        deck.drawCard()

    assert deck.size == 0

def test_recycled_discard_pile_can_be_shuffled(monkeypatch):
    deck = Deck()
    drawnCards = [deck.drawCard() for _ in range(52)]

    for card in drawnCards:
        deck.discardCard(card)

    shuffleCalls = []
    monkeypatch.setattr("cards.random.shuffle", lambda cards: shuffleCalls.append(cards.copy()))

    deck.recycleDiscardPile(shuffle=True)

    assert shuffleCalls == [drawnCards]