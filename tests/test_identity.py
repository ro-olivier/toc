import pytest

from uuid import UUID

from identity import JOIN_CODE_ALPHABET, JOIN_CODE_LENGTH, createJoinCode, createPlayerId, createResumeToken, createSessionId, hashResumeToken, resumeTokenMatches


def test_join_code_uses_unambiguous_alphabet():
	joinCode = createJoinCode()

	assert len(joinCode) == JOIN_CODE_LENGTH
	assert set(joinCode).issubset(set(JOIN_CODE_ALPHABET))


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