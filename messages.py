RESERVED_MESSAGE_FIELDS = {"type", "messageKey", "parameters", "fallback", "msg"}


def build_message(messageType: str, messageKey: str, fallback: str, parameters: dict | None = None, **payload) -> dict:
	if not isinstance(messageType, str) or not messageType:
		raise ValueError("Message type must be a non-empty string")

	if not isinstance(messageKey, str) or not messageKey:
		raise ValueError("Message key must be a non-empty string")

	if not isinstance(fallback, str) or not fallback:
		raise ValueError("Message fallback must be a non-empty string")

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