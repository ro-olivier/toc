import hashlib
import secrets
import uuid


JOIN_CODE_ADJECTIVES = (
	"amber",
	"brave",
	"bright",
	"calm",
	"clever",
	"cool",
	"coral",
	"cosy",
	"crimson",
	"daring",
	"eager",
	"gentle",
	"golden",
	"happy",
	"jolly",
	"kind",
	"lively",
	"lucky",
	"merry",
	"mighty",
	"nimble",
	"quiet",
	"rapid",
	"royal",
	"silver",
	"steady",
	"sunny",
	"swift",
	"vivid",
	"warm",
	"wild",
	"wise",
)

JOIN_CODE_NOUNS = (
	"badger",
	"bear",
	"beaver",
	"bison",
	"cat",
	"crane",
	"deer",
	"dog",
	"dolphin",
	"eagle",
	"falcon",
	"fox",
	"frog",
	"goat",
	"hare",
	"heron",
	"horse",
	"lynx",
	"moose",
	"otter",
	"owl",
	"panda",
	"rabbit",
	"raven",
	"seal",
	"shark",
	"swan",
	"tiger",
	"turtle",
	"whale",
	"wolf",
	"yak",
)
RESUME_TOKEN_BYTES = 32


def createJoinCode() -> str:
	adjective = secrets.choice(JOIN_CODE_ADJECTIVES)
	noun = secrets.choice(JOIN_CODE_NOUNS)
	return f"{adjective}-{noun}"

def normalizeJoinCode(joinCode: str) -> str:
	if type(joinCode) is not str:
		raise ValueError("Join code must be a string")

	normalizedCode = joinCode.strip().lower()

	if not normalizedCode:
		raise ValueError("Join code cannot be empty")

	return normalizedCode


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

def createSeatId() -> str:
	return uuid.uuid4().hex