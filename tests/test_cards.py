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
