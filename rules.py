from dataclasses import dataclass
from enum import StrEnum


class ShuffleMode(StrEnum):
	NEVER = "never"
	ON_DEALER_CHANGE = "on_dealer_change"
	ON_DEALER_CYCLE = "on_dealer_cycle"


class Rotation(StrEnum):
	CLOCKWISE = "clockwise"
	COUNTERCLOCKWISE = "counterclockwise"


class FiveBehaviour(StrEnum):
	FORCE_MOVE_OPPONENT = "force_move_opponent"
	NORMAL_MOVE_BY_FIVE = "normal_move_by_five"
	BOTH = "both"


class SevenHopping(StrEnum):
	DISABLED = "disabled"
	OPTIONAL = "optional"
	FORCED = "forced"


class FiveHopDecider(StrEnum):
	ACTING_PLAYER = "acting_player"
	PIECE_OWNER = "piece_owner"


@dataclass(frozen=True, slots=True)
class GameRules:
	card_exchange: bool = True
	exit_spot_is_protected_and_blocking: bool = True
	house_spots_are_blocking_and_protected: bool = True
	landing_on_occupied_spot_kicks_piece: bool = True

	shuffle_cards: ShuffleMode = ShuffleMode.NEVER
	rotation: Rotation = Rotation.CLOCKWISE
	deal_card_counts: tuple[int, ...] = (5, 4, 4)

	track_region_length: int = 18
	enter_house_at_spot: int = 18
	cannot_play_folds_entire_hand: bool = True

	four_can_move_backward: bool = True
	can_enter_house_backward: bool = False

	five_behaviour: FiveBehaviour = FiveBehaviour.FORCE_MOVE_OPPONENT

	seven_can_split: bool = True
	seven_split_kicks_pieces_on_path: bool = True
	seven_hopping: SevenHopping = SevenHopping.OPTIONAL
	five_hop_decider: FiveHopDecider = FiveHopDecider.ACTING_PLAYER
	seven_hopping_on_four_backward_goes_backward: bool = False

	jacks_can_switch: bool = True
	jacks_can_switch_then_seven_hop: bool = False

	ace_values: tuple[int, ...] = (1, 11)
	king_kicks_pieces_on_path: bool = False


MONTSURVENT_RULES = GameRules()
RULE_PRESETS = {"montsurvent": MONTSURVENT_RULES}
