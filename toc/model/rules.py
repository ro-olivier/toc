from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from typing import get_type_hints

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

ENUM_RULE_FIELDS = {
	"shuffle_cards": ShuffleMode,
	"rotation": Rotation,
	"five_behaviour": FiveBehaviour,
	"seven_hopping": SevenHopping,
	"five_hop_decider": FiveHopDecider,
}

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

	def __post_init__(self) -> None:
		for fieldName, fieldType in get_type_hints(type(self)).items():
			if fieldType is bool and type(getattr(self, fieldName)) is not bool:
				raise ValueError(f"Rule '{fieldName}' must be a boolean")

		for fieldName, enumClass in ENUM_RULE_FIELDS.items():
			if not isinstance(getattr(self, fieldName), enumClass):
				raise ValueError(f"Rule '{fieldName}' must be one of: {', '.join(option.value for option in enumClass)}")

		if type(self.track_region_length) is not int or self.track_region_length not in (16, 18):
			raise ValueError("Track region length must be 16 or 18")

		if type(self.enter_house_at_spot) is not int or self.enter_house_at_spot not in (16, 18):
			raise ValueError("House entry position must be 16 or 18")

		if self.enter_house_at_spot > self.track_region_length:
			raise ValueError("House entry position cannot exceed the track region length")

		if type(self.deal_card_counts) is not tuple or any(type(cardCount) is not int for cardCount in self.deal_card_counts) or len(self.deal_card_counts) != 3 or sorted(self.deal_card_counts) != [4, 4, 5]:
			raise ValueError("Deal card counts must contain one 5-card deal and two 4-card deals")

		if type(self.ace_values) is not tuple or any(type(aceValue) is not int for aceValue in self.ace_values) or self.ace_values not in ((1,), (11,), (1, 11)):
			raise ValueError("Ace values must be (1,), (11,) or (1, 11)")

	def to_dict(self) -> dict:
		result = asdict(self)

		for fieldName in ENUM_RULE_FIELDS:
			result[fieldName] = getattr(self, fieldName).value

		result["deal_card_counts"] = list(self.deal_card_counts)
		result["ace_values"] = list(self.ace_values)
		return result

	@classmethod
	def from_dict(cls, values: dict) -> "GameRules":
		if type(values) is not dict:
			raise ValueError("Rules must be provided as an object")

		validFields = {field.name for field in fields(cls)}
		unknownFields = set(values) - validFields

		if unknownFields:
			raise ValueError(f"Unknown rule fields: {', '.join(sorted(unknownFields))}")

		convertedValues = values.copy()

		for fieldName, enumClass in ENUM_RULE_FIELDS.items():
			if fieldName not in convertedValues:
				continue

			try:
				convertedValues[fieldName] = enumClass(convertedValues[fieldName])
			except (TypeError, ValueError) as error:
				raise ValueError(f"Invalid value for rule '{fieldName}'") from error

		for fieldName in ("deal_card_counts", "ace_values"):
			if fieldName in convertedValues:
				if not isinstance(convertedValues[fieldName], (list, tuple)):
					raise ValueError(f"Rule '{fieldName}' must be an array")

				convertedValues[fieldName] = tuple(convertedValues[fieldName])

		return cls(**convertedValues)


MONTSURVENT_RULES = GameRules()
DEFAULT_RULE_PRESET = "montsurvent"
RULE_PRESETS = {"montsurvent": MONTSURVENT_RULES}

RULE_CHOICE_OPTIONS = {
	"deal_card_counts": [[5, 4, 4], [4, 5, 4], [4, 4, 5]],
	"track_region_length": [18, 16],
	"enter_house_at_spot": [18, 16],
	"ace_values": [[1, 11], [1], [11]],
}

def get_matching_preset_name(rules: GameRules) -> str:
	for presetName, presetRules in RULE_PRESETS.items():
		if rules == presetRules:
			return presetName

	return "custom"

def get_rule_schema() -> dict:
	typeHints = get_type_hints(GameRules)
	schema = {}

	for field in fields(GameRules):
		if typeHints[field.name] is bool:
			schema[field.name] = {"type": "boolean"}
		elif field.name in ENUM_RULE_FIELDS:
			schema[field.name] = {"type": "choice", "options": [option.value for option in ENUM_RULE_FIELDS[field.name]]}
		elif field.name in RULE_CHOICE_OPTIONS:
			options = [option.copy() if isinstance(option, list) else option for option in RULE_CHOICE_OPTIONS[field.name]]
			schema[field.name] = {"type": "choice", "options": options}
		else:
			raise RuntimeError(f"No form schema is defined for rule '{field.name}'")

	return schema

def resolve_ruleset(presetName: str = DEFAULT_RULE_PRESET, customValues: dict = None) -> GameRules:
	if type(presetName) is not str:
		raise ValueError("Rule preset name must be a string")

	if presetName == "custom":
		if customValues is None:
			raise ValueError("Custom rules must be provided when using the custom preset")

		return GameRules.from_dict(customValues)

	if customValues is not None:
		raise ValueError("Custom rule values can only be used with the custom preset")

	if presetName not in RULE_PRESETS:
		raise ValueError(f"Unknown rule preset: {presetName}")

	return RULE_PRESETS[presetName]