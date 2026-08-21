import hashlib
import secrets
import uuid


JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 6
RESUME_TOKEN_BYTES = 32


def createJoinCode() -> str:
	return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


def createSessionId() -> str:
	return uuid.uuid4().hex


def createPlayerId() -> str:
	return uuid.uuid4().hex


def createResumeToken() -> str:
	return secrets.token_urlsafe(RESUME_TOKEN_BYTES)


def hashResumeToken(token: str) -> str:
	if not isinstance(token, str) or not token:
		raise ValueError("Resume token must be a non-empty string")

	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def resumeTokenMatches(token: str, expectedHash: str) -> bool:
	if not isinstance(token, str) or not token:
		return False

	if not isinstance(expectedHash, str) or not expectedHash:
		return False

	return secrets.compare_digest(hashResumeToken(token), expectedHash)