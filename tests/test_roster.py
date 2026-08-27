import pytest

from toc.infrastructure.identity import createPlayerId, createResumeToken, hashResumeToken
from toc.model.player import Player
from toc.session.roster import Participant, PlayerSeat, SessionRoster
from toc.model.game_mode import DuelFourLayout, GameMode, getGameModeDefinition


def makeParticipant(name: str) -> Participant:
	return Participant(
		participantId=createPlayerId(),
		routerId=f"TEST-{name}",
		name=name,
		resumeTokenHash=hashResumeToken(createResumeToken()),
	)


def makeSeat(participant: Participant, team: str, color: str) -> PlayerSeat:
	player = Player(participant.routerId, participant.name, team=team, color=color)

	return PlayerSeat(
		seatId=createPlayerId(),
		participantId=participant.participantId,
		team=team,
		color=color,
		player=player,
	)


def test_roster_registers_participant():
	roster = SessionRoster()
	alice = makeParticipant("Alice")

	roster.addParticipant(alice)

	assert roster.participantCount == 1
	assert roster.getParticipantByRouterId("TEST-Alice") is alice
	assert roster.getParticipantById(alice.participantId) is alice


def test_participant_can_control_multiple_seats():
	roster = SessionRoster()
	alice = makeParticipant("Alice")
	redSeat = makeSeat(alice, "0", "red")
	blueSeat = makeSeat(alice, "0", "blue")

	roster.addParticipant(alice)
	roster.addSeat(redSeat)
	roster.addSeat(blueSeat)

	assert roster.seatCount == 2
	assert alice.seatIds == [redSeat.seatId, blueSeat.seatId]
	assert alice.controlsSeat(redSeat.seatId)
	assert alice.controlsSeat(blueSeat.seatId)
	assert roster.getParticipantForPlayer(redSeat.player) is alice
	assert roster.getParticipantForPlayer(blueSeat.player) is alice


def test_different_participants_can_belong_to_same_team():
	roster = SessionRoster()
	alice = makeParticipant("Alice")
	bob = makeParticipant("Bob")
	redSeat = makeSeat(alice, "0", "red")
	greenSeat = makeSeat(bob, "0", "green")

	roster.addParticipant(alice)
	roster.addParticipant(bob)
	roster.addSeat(redSeat)
	roster.addSeat(greenSeat)

	assert redSeat.team == greenSeat.team
	assert roster.getParticipantForSeat(redSeat) is alice
	assert roster.getParticipantForSeat(greenSeat) is bob


def test_roster_rejects_seat_for_unknown_participant():
	roster = SessionRoster()
	alice = makeParticipant("Alice")
	redSeat = makeSeat(alice, "0", "red")

	with pytest.raises(ValueError, match="unknown participant"):
		roster.addSeat(redSeat)


def test_roster_rejects_duplicate_seat_color():
	roster = SessionRoster()
	alice = makeParticipant("Alice")
	bob = makeParticipant("Bob")

	roster.addParticipant(alice)
	roster.addParticipant(bob)
	roster.addSeat(makeSeat(alice, "0", "red"))

	with pytest.raises(ValueError, match="colour is already registered"):
		roster.addSeat(makeSeat(bob, "1", "red"))


def test_roster_rejects_duplicate_participant_name():
	roster = SessionRoster()
	firstAlice = makeParticipant("Alice")
	secondAlice = makeParticipant("Alice")
	secondAlice.routerId = "TEST-Other-Alice"

	roster.addParticipant(firstAlice)

	with pytest.raises(ValueError, match="name is already registered"):
		roster.addParticipant(secondAlice)

def test_team_four_seats_are_ordered_by_alternating_teams():
	roster = SessionRoster()
	alice = makeParticipant("Alice")
	bob = makeParticipant("Bob")
	carol = makeParticipant("Carol")
	diana = makeParticipant("Diana")

	for participant in (alice, bob, carol, diana):
		roster.addParticipant(participant)

	aliceSeat = makeSeat(alice, "0", "red")
	bobSeat = makeSeat(bob, "0", "blue")
	carolSeat = makeSeat(carol, "1", "green")
	dianaSeat = makeSeat(diana, "1", "yellow")

	for seat in (aliceSeat, bobSeat, carolSeat, dianaSeat):
		roster.addSeat(seat)

	order = roster.determineSeatOrder(getGameModeDefinition(GameMode.TEAM_FOUR))

	assert order == (aliceSeat.seatId, carolSeat.seatId, bobSeat.seatId, dianaSeat.seatId)


def test_team_four_order_starts_with_first_participants_team():
	roster = SessionRoster()
	alice = makeParticipant("Alice")
	bob = makeParticipant("Bob")
	carol = makeParticipant("Carol")
	diana = makeParticipant("Diana")

	for participant in (alice, bob, carol, diana):
		roster.addParticipant(participant)

	aliceSeat = makeSeat(alice, "1", "red")
	bobSeat = makeSeat(bob, "0", "blue")
	carolSeat = makeSeat(carol, "1", "green")
	dianaSeat = makeSeat(diana, "0", "yellow")

	for seat in (aliceSeat, bobSeat, carolSeat, dianaSeat):
		roster.addSeat(seat)

	order = roster.determineSeatOrder(getGameModeDefinition(GameMode.TEAM_FOUR))

	assert order == (aliceSeat.seatId, bobSeat.seatId, carolSeat.seatId, dianaSeat.seatId)


@pytest.mark.parametrize(
	("layout", "expectedColors"),
	[
		(DuelFourLayout.ADJACENT, ("red", "blue", "green", "yellow")),
		(DuelFourLayout.CROSS, ("red", "green", "blue", "yellow")),
	],
)
def test_duel_four_layout_controls_seat_order(layout, expectedColors):
	roster = SessionRoster()
	alice = makeParticipant("Alice")
	bob = makeParticipant("Bob")

	roster.addParticipant(alice)
	roster.addParticipant(bob)

	for seat in (
		makeSeat(alice, "0", "red"),
		makeSeat(alice, "0", "blue"),
		makeSeat(bob, "1", "green"),
		makeSeat(bob, "1", "yellow"),
	):
		roster.addSeat(seat)

	definition = getGameModeDefinition(GameMode.DUEL_FOUR, layout)
	order = roster.determineSeatOrder(definition)
	orderedColors = tuple(roster.getSeatById(seatId).color for seatId in order)

	assert orderedColors == expectedColors