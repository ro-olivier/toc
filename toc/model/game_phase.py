from enum import StrEnum


class GamePhase(StrEnum):
	DEAL_START = "deal-start"
	CARD_EXCHANGE = "card-exchange"
	TURN_START = "turn-start"
	TURN_DECISION = "turn-decision"
	SEVEN_SPLIT = "seven-split"
	SEVEN_HOP = "seven-hop"
	DEAL_END = "deal-end"
	DECK_CYCLE_END = "deck-cycle-end"
	FINISHED = "finished"
	TURN_END = "turn-end"