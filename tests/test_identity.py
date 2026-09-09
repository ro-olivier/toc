import pytest

from uuid import UUID

from toc.infrastructure.identity import JOIN_CODE_ADJECTIVES, JOIN_CODE_NOUNS, createJoinCode, createPlayerId, createResumeToken, createSessionId, hashResumeToken, resumeTokenMatches, createSeatId, normalizeJoinCode


def test_join_code_uses_adjective_and_noun():
	joinCode = createJoinCode()
	parts = joinCode.split("-")

	assert len(parts) == 2
	assert parts[0] in JOIN_CODE_ADJECTIVES
	assert parts[1] in JOIN_CODE_NOUNS
	assert joinCode == joinCode.lower()
	assert " " not in joinCode

def test_join_code_combines_selected_words(monkeypatch):
	monkeypatch.setattr("toc.infrastructure.identity.secrets.choice", lambda words: words[0])

	assert createJoinCode() == f"{JOIN_CODE_ADJECTIVES[0]}-{JOIN_CODE_NOUNS[0]}"


@pytest.mark.parametrize("factory", [createSessionId, createPlayerId])
def test_persistent_ids_are_uuid_hex_strings(factory):
	identifier = factory()

	assert UUID(hex=identifier).hex == identifier


def test_resume_token_matches_its_hash():
	token = createResumeToken()
	tokenHash = hashResumeToken(token)

	assert token != tokenHash
	assert len(tokenHash) == 64
	assert resumeTokenMatches(token, tokenHash)


def test_incorrect_resume_token_is_rejected():
	tokenHash = hashResumeToken(createResumeToken())

	assert not resumeTokenMatches(createResumeToken(), tokenHash)
	assert not resumeTokenMatches("", tokenHash)
	assert not resumeTokenMatches("something", "")

def test_seat_ids_are_unique_uuid_hex_values():
	firstSeatId = createSeatId()
	secondSeatId = createSeatId()

	assert firstSeatId != secondSeatId
	assert UUID(hex=firstSeatId).hex == firstSeatId
	assert UUID(hex=secondSeatId).hex == secondSeatId

def test_join_code_normalization_is_case_insensitive():
	assert normalizeJoinCode("  Calm-Otter  ") == "calm-otter"


@pytest.mark.parametrize("joinCode", ["", "   ", None, 123])
def test_invalid_join_code_cannot_be_normalized(joinCode):
	with pytest.raises(ValueError):
		normalizeJoinCode(joinCode)