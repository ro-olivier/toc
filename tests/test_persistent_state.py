import json

import pytest

from toc.infrastructure.identity import createPlayerId, createResumeToken, hashResumeToken
from toc.session.game_session import GameSession
from toc.session.input_router import PlayerInputRouter
from toc.persistence.persistent_state import ParticipantMetadataState, SeatMetadataState, SessionMetadataState
from toc.infrastructure.versions import ARCHIVE_FORMAT_VERSION, ENGINE_VERSION, RULES_FORMAT_VERSION
from toc.model.game_mode import DuelFourLayout, GameMode, getGameModeDefinition
from toc.model.player import Player
from toc.session.roster import Participant, PlayerSeat
from toc.session.session_participant import SessionParticipant


def makeSessionWithPlayer():
	session = GameSession("ABCDEF", PlayerInputRouter())
	resumeToken = createResumeToken()
	participantId = createPlayerId()
	routerId = "ABCDEF-Alice"
	resumeTokenHash = hashResumeToken(resumeToken)

	participant = Participant(
		participantId=participantId,
		routerId=routerId,
		name="Alice",
		resumeTokenHash=resumeTokenHash,
		websocket=object(),
		active=True,
		configured=True,
	)

	player = Player(identifier=participantId, name="Alice", team="0", color="red", routerId=routerId)
	seat = PlayerSeat(seatId=participantId, participantId=participantId, team="0", color="red", player=player)

	session.roster.addParticipant(participant)
	session.roster.addSeat(seat)

	sessionParticipant = SessionParticipant(participant, player)
	sessionParticipant.configureSeats([seat])
	session.participants[routerId] = sessionParticipant

	return session, resumeToken


def test_session_metadata_contains_only_persistent_data():
	session, resumeToken = makeSessionWithPlayer()

	state = session.metadataState()
	payload = state.to_dict()
	encoded = json.dumps(payload)

	assert payload["archiveFormatVersion"] == ARCHIVE_FORMAT_VERSION
	assert payload["engineVersion"] == ENGINE_VERSION
	assert payload["rulesFormatVersion"] == RULES_FORMAT_VERSION
	assert payload["sessionId"] == session.sessionId
	assert payload["joinCode"] == "ABCDEF"

	assert payload["participants"][0]["name"] == "Alice"
	assert payload["seats"][0]["team"] == "0"
	assert payload["seats"][0]["color"] == "red"

	assert "websocket" not in payload["participants"][0]
	assert "active" not in payload["participants"][0]
	assert "object" not in payload["seats"][0]
	assert resumeToken not in encoded


def test_session_metadata_survives_json_round_trip():
	session, _ = makeSessionWithPlayer()

	originalState = session.metadataState()
	encoded = json.dumps(originalState.to_dict())
	restoredState = SessionMetadataState.from_dict(json.loads(encoded))

	assert restoredState == originalState
	assert restoredState.rules == session.rules
	assert restoredState.participants == originalState.participants
	assert restoredState.seats == originalState.seats
	assert restoredState.modeDefinition == session.modeDefinition


def test_unknown_archive_format_is_rejected():
	session, _ = makeSessionWithPlayer()
	payload = session.metadataState().to_dict()
	payload["archiveFormatVersion"] = 999

	with pytest.raises(ValueError, match="Unsupported archive format version"):
		SessionMetadataState.from_dict(payload)


def test_unknown_rules_format_is_rejected():
	session, _ = makeSessionWithPlayer()
	payload = session.metadataState().to_dict()
	payload["rulesFormatVersion"] = 999

	with pytest.raises(ValueError, match="Unsupported rules format version"):
		SessionMetadataState.from_dict(payload)

def test_session_metadata_preserves_non_default_game_mode():
	modeDefinition = getGameModeDefinition(GameMode.DUEL_FOUR, DuelFourLayout.ADJACENT)
	session = GameSession("ABCDEF", PlayerInputRouter(), modeDefinition=modeDefinition)

	restoredState = SessionMetadataState.from_dict(json.loads(json.dumps(session.metadataState().to_dict())))

	assert restoredState.modeDefinition == modeDefinition
	assert restoredState.modeDefinition.mode is GameMode.DUEL_FOUR
	assert restoredState.modeDefinition.layout is DuelFourLayout.ADJACENT

def test_participant_metadata_survives_json_round_trip():
	participant = Participant(
		participantId=createPlayerId(),
		routerId="TEST-Alice",
		name="Alice",
		resumeTokenHash=hashResumeToken(createResumeToken()),
		configured=True,
	)

	originalState = ParticipantMetadataState.fromParticipant(participant)
	restoredState = ParticipantMetadataState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.participantId == participant.participantId
	assert restoredState.name == "Alice"
	assert restoredState.configured is True


def test_seat_metadata_survives_json_round_trip():
	participantId = createPlayerId()
	player = Player(identifier=createPlayerId(), name="Alice", team="0", color="red")
	seat = PlayerSeat(seatId=player.identifier, participantId=participantId, team="0", color="red", player=player)

	originalState = SeatMetadataState.fromSeat(seat)
	restoredState = SeatMetadataState.from_dict(json.loads(json.dumps(originalState.to_dict())))

	assert restoredState == originalState
	assert restoredState.seatId == player.identifier
	assert restoredState.participantId == participantId
	assert restoredState.team == "0"
	assert restoredState.color == "red"


def test_two_seats_can_reference_same_persistent_participant():
	participantId = createPlayerId()
	redPlayer = Player(identifier=createPlayerId(), name="Alice", team="0", color="red")
	bluePlayer = Player(identifier=createPlayerId(), name="Alice", team="0", color="blue")
	redSeat = SeatMetadataState.fromSeat(PlayerSeat(redPlayer.identifier, participantId, "0", "red", redPlayer))
	blueSeat = SeatMetadataState.fromSeat(PlayerSeat(bluePlayer.identifier, participantId, "0", "blue", bluePlayer))

	assert redSeat.seatId != blueSeat.seatId
	assert redSeat.participantId == blueSeat.participantId