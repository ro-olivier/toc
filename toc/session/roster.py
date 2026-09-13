from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from toc.model.player import Player
from toc.model.game_mode import GameModeDefinition

if TYPE_CHECKING:
	from starlette.websockets import WebSocket


def _validatePersistentId(value: str, fieldName: str) -> None:
	if type(value) is not str:
		raise ValueError(f"Invalid {fieldName}")

	try:
		normalisedId = UUID(hex=value).hex
	except (TypeError, ValueError, AttributeError) as error:
		raise ValueError(f"Invalid {fieldName}") from error

	if normalisedId != value:
		raise ValueError(f"Invalid {fieldName}")


@dataclass(slots=True)
class Participant:
	participantId: str
	routerId: str
	name: str
	resumeTokenHash: str
	websocket: WebSocket | None = None
	active: bool = False
	configured: bool = False
	seatIds: list[str] = field(default_factory=list)

	def __post_init__(self) -> None:
		_validatePersistentId(self.participantId, "participant ID")

		if type(self.routerId) is not str or not self.routerId:
			raise ValueError("Invalid participant router ID")

		if type(self.name) is not str or not self.name:
			raise ValueError("Invalid participant name")

		if type(self.resumeTokenHash) is not str or len(self.resumeTokenHash) != 64:
			raise ValueError("Invalid resume token hash")

		try:
			int(self.resumeTokenHash, 16)
		except ValueError as error:
			raise ValueError("Invalid resume token hash") from error

		if type(self.active) is not bool or type(self.configured) is not bool:
			raise ValueError("Invalid participant state")

	def assignSeat(self, seatId: str) -> None:
		_validatePersistentId(seatId, "seat ID")

		if seatId in self.seatIds:
			raise ValueError("Seat is already assigned to this participant")

		self.seatIds.append(seatId)

	def controlsSeat(self, seatId: str) -> bool:
		return seatId in self.seatIds


@dataclass(slots=True)
class PlayerSeat:
	seatId: str
	participantId: str
	team: str
	color: str
	player: Player

	def __post_init__(self) -> None:
		_validatePersistentId(self.seatId, "seat ID")
		_validatePersistentId(self.participantId, "participant ID")

		if type(self.team) is not str or not self.team:
			raise ValueError("Invalid seat team")

		if type(self.color) is not str or not self.color:
			raise ValueError("Invalid seat colour")

		if not isinstance(self.player, Player):
			raise ValueError("Invalid seat player")


class SessionRoster:
	def __init__(self) -> None:
		self._participantsByRouterId: dict[str, Participant] = {}
		self._participantsById: dict[str, Participant] = {}
		self._seatsById: dict[str, PlayerSeat] = {}
		self._seatsByPlayer: dict[Player, PlayerSeat] = {}

	@property
	def participants(self) -> tuple[Participant, ...]:
		return tuple(self._participantsByRouterId.values())

	@property
	def seats(self) -> tuple[PlayerSeat, ...]:
		return tuple(self._seatsById.values())

	@property
	def participantCount(self) -> int:
		return len(self._participantsByRouterId)

	@property
	def seatCount(self) -> int:
		return len(self._seatsById)

	def addParticipant(self, participant: Participant) -> None:
		if not isinstance(participant, Participant):
			raise ValueError("Invalid participant")

		if participant.routerId in self._participantsByRouterId:
			raise ValueError("Participant router ID is already registered")

		if participant.participantId in self._participantsById:
			raise ValueError("Participant ID is already registered")

		if any(existing.name == participant.name for existing in self.participants):
			raise ValueError("Participant name is already registered")

		self._participantsByRouterId[participant.routerId] = participant
		self._participantsById[participant.participantId] = participant

	def addSeat(self, seat: PlayerSeat) -> None:
		if not isinstance(seat, PlayerSeat):
			raise ValueError("Invalid player seat")

		if seat.participantId not in self._participantsById:
			raise ValueError("Seat references an unknown participant")

		if seat.seatId in self._seatsById:
			raise ValueError("Seat ID is already registered")

		if seat.player in self._seatsByPlayer:
			raise ValueError("Player is already assigned to a seat")

		if any(existing.color == seat.color for existing in self.seats):
			raise ValueError("Seat colour is already registered")

		participant = self._participantsById[seat.participantId]
		participant.assignSeat(seat.seatId)
		self._seatsById[seat.seatId] = seat
		self._seatsByPlayer[seat.player] = seat

	def getParticipantByRouterId(self, routerId: str) -> Participant:
		try:
			return self._participantsByRouterId[routerId]
		except KeyError as error:
			raise ValueError(f"Unknown participant router ID: {routerId}") from error

	def getParticipantById(self, participantId: str) -> Participant:
		try:
			return self._participantsById[participantId]
		except KeyError as error:
			raise ValueError(f"Unknown participant ID: {participantId}") from error

	def getSeatById(self, seatId: str) -> PlayerSeat:
		try:
			return self._seatsById[seatId]
		except KeyError as error:
			raise ValueError(f"Unknown seat ID: {seatId}") from error

	def getSeatForPlayer(self, player: Player) -> PlayerSeat:
		try:
			return self._seatsByPlayer[player]
		except KeyError as error:
			raise ValueError("Player is not assigned to a seat") from error

	def getParticipantForSeat(self, seat: PlayerSeat) -> Participant:
		return self.getParticipantById(seat.participantId)

	def getParticipantForPlayer(self, player: Player) -> Participant:
		return self.getParticipantForSeat(self.getSeatForPlayer(player))

	def getSeatsForParticipant(self, participantId: str) -> tuple[PlayerSeat, ...]:
		participant = self.getParticipantById(participantId)
		return tuple(self.getSeatById(seatId) for seatId in participant.seatIds)

	def determineSeatOrder(self, modeDefinition: GameModeDefinition) -> tuple[str, ...]:
		if not isinstance(modeDefinition, GameModeDefinition):
			raise ValueError("Invalid game-mode definition")

		if self.participantCount != modeDefinition.participantCount:
			raise ValueError("Participant count does not match game mode")

		if self.seatCount != modeDefinition.seatCount:
			raise ValueError("Seat count does not match game mode")

		participants = list(self.participants)
		participantTeams: dict[str, str] = {}

		for participant in participants:
			seats = self.getSeatsForParticipant(participant.participantId)
			teams = {seat.team for seat in seats}

			if len(teams) != 1:
				raise ValueError("Participant seats must all belong to one team")

			participantTeams[participant.participantId] = next(iter(teams))

		firstTeam = participantTeams[participants[0].participantId]

		if firstTeam not in modeDefinition.teamIds:
			raise ValueError("Participant belongs to an invalid team")

		firstTeamIndex = modeDefinition.teamIds.index(firstTeam)
		actualTeamOrder = modeDefinition.teamIds[firstTeamIndex:] + modeDefinition.teamIds[:firstTeamIndex]
		teamMapping = {abstractTeamIndex: actualTeamOrder[abstractTeamIndex] for abstractTeamIndex in range(modeDefinition.teamCount)}
		participantsByAbstractIndex: dict[int, Participant] = {}

		for abstractTeamIndex in range(modeDefinition.teamCount):
			actualTeam = teamMapping[abstractTeamIndex]
			abstractParticipantIndexes = [
				participantIndex
				for participantIndex, teamIndex in enumerate(modeDefinition.participantTeamPattern)
				if teamIndex == abstractTeamIndex
			]
			actualParticipants = [
				participant
				for participant in participants
				if participantTeams[participant.participantId] == actualTeam
			]

			if len(actualParticipants) != len(abstractParticipantIndexes):
				raise ValueError("Team participant count does not match game mode")

			for participantIndex, participant in zip(abstractParticipantIndexes, actualParticipants):
				participantsByAbstractIndex[participantIndex] = participant

		seatOffsets: dict[str, int] = {participant.participantId: 0 for participant in participants}
		orderedSeatIds: list[str] = []

		for participantIndex in modeDefinition.participantPattern:
			participant = participantsByAbstractIndex[participantIndex]
			participantSeats = self.getSeatsForParticipant(participant.participantId)
			seatOffset = seatOffsets[participant.participantId]

			if seatOffset >= len(participantSeats):
				raise ValueError("Participant does not control enough seats")

			orderedSeatIds.append(participantSeats[seatOffset].seatId)
			seatOffsets[participant.participantId] += 1

		if any(seatOffsets[participant.participantId] != len(self.getSeatsForParticipant(participant.participantId)) for participant in participants):
			raise ValueError("Participant controls too many seats")

		return tuple(orderedSeatIds)

	def removeSeat(self, seatId: str) -> PlayerSeat:
		seat = self.getSeatById(seatId)
		participant = self.getParticipantById(seat.participantId)

		del self._seatsById[seatId]
		del self._seatsByPlayer[seat.player]
		participant.seatIds.remove(seatId)

		return seat