RESERVED_MESSAGE_FIELDS = {"type", "messageKey", "parameters", "fallback", "msg"}
MESSAGE_KEYS = frozenset({
	"connection.player_disconnected",
	"connection.player_rejoined",
	"connection.rejoined_self",
	"errors.creation_data_object",
	"errors.internal_game_error",
	"errors.invalid_game_configuration",
	"errors.invalid_json_message",
	"errors.invalid_message_format",
	"errors.unknown_creation_fields",
	"gameplay.card_discarded",
	"gameplay.card_exchange_complete",
	"gameplay.deal_finished",
	"gameplay.deal_started",
	"gameplay.folded_player_skipped",
	"gameplay.forced_play",
	"gameplay.game_starting",
	"gameplay.next_player",
	"gameplay.piece_deployed",
	"gameplay.piece_moved",
	"gameplay.pieces_switched",
	"gameplay.player_folded",
	"gameplay.seven_split_started",
	"gameplay.team_won",
	"gameplay.turn_ended",
	"lobby.errors.already_confirmed",
	"lobby.errors.color_taken",
	"lobby.errors.invalid_color",
	"lobby.errors.invalid_team",
	"lobby.errors.team_full",
	"prompts.card_unplayable",
	"prompts.choose_card",
	"prompts.choose_origin",
	"prompts.choose_target",
	"prompts.discard_card",
	"prompts.exchange_card",
	"prompts.seven_hop",
	"errors.unknown_message_type",
})

def build_message(messageType: str, messageKey: str, fallback: str, parameters: dict | None = None, **payload) -> dict:
	if not isinstance(messageType, str) or not messageType:
		raise ValueError("Message type must be a non-empty string")

	if not isinstance(messageKey, str) or not messageKey:
		raise ValueError("Message key must be a non-empty string")

	if not isinstance(fallback, str) or not fallback:
		raise ValueError("Message fallback must be a non-empty string")

	if messageKey not in MESSAGE_KEYS:
		raise ValueError(f"Unknown translatable message key: {messageKey}")

	if parameters is not None and not isinstance(parameters, dict):
		raise ValueError("Message parameters must be a dictionary")

	conflictingFields = RESERVED_MESSAGE_FIELDS.intersection(payload)
	if conflictingFields:
		raise ValueError(f"Reserved message fields cannot be passed as payload: {', '.join(sorted(conflictingFields))}")

	message = {
		"type": messageType,
		"messageKey": messageKey,
		"parameters": dict(parameters) if parameters is not None else {},
		"fallback": fallback,
	}
	message.update(payload)
	return message