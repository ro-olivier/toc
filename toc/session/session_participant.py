from dataclasses import dataclass, field

from toc.model.player import Player
from toc.session.roster import Participant, PlayerSeat


@dataclass(slots=True)
class SessionParticipant:
	participant: Participant
	primaryPlayer: Player | None = None
	controlledPlayers: list[Player] = field(default_factory=list)
	primarySeat: PlayerSeat | None = None
	controlledSeats: list[PlayerSeat] = field(default_factory=list)

	def __post_init__(self) -> None:
		if not isinstance(self.participant, Participant):
			raise TypeError("A participant is required")

		if self.primaryPlayer is not None and not isinstance(self.primaryPlayer, Player):
			raise TypeError("Primary player must be a Player")

	@property
	def name(self) -> str:
		return self.participant.name

	@property
	def routerId(self) -> str:
		return self.participant.routerId

	@property
	def participantId(self) -> str:
		return self.participant.participantId

	@property
	def resumeTokenHash(self) -> str:
		return self.participant.resumeTokenHash

	@property
	def websocket(self) -> object | None:
		return self.participant.websocket

	@websocket.setter
	def websocket(self, websocket: object | None) -> None:
		self.participant.websocket = websocket

	@property
	def active(self) -> bool:
		return self.participant.active

	@active.setter
	def active(self, active: bool) -> None:
		self.participant.active = active

	@property
	def configured(self) -> bool:
		return self.participant.configured

	@configured.setter
	def configured(self, configured: bool) -> None:
		self.participant.configured = configured

	@property
	def team(self) -> str:
		return "" if self.primarySeat is None else self.primarySeat.team

	@property
	def color(self) -> str:
		return "" if self.primarySeat is None else self.primarySeat.color

	@property
	def colors(self) -> list[str]:
		return [seat.color for seat in self.controlledSeats]

	def addSeat(self, seat: PlayerSeat) -> None:
		if not isinstance(seat, PlayerSeat):
			raise TypeError("A player seat is required")

		if seat.participantId != self.participantId:
			raise ValueError("Seat belongs to another participant")

		if self.controlledSeats and seat.team != self.controlledSeats[0].team:
			raise ValueError("Participant cannot control seats from different teams")

		self.controlledPlayers.append(seat.player)
		self.controlledSeats.append(seat)

		if self.primarySeat is None:
			self.primaryPlayer = seat.player
			self.primarySeat = seat

	def configureSeats(self, seats: list[PlayerSeat]) -> None:
		if not seats:
			raise ValueError("A configured participant must control at least one seat")

		if self.controlledSeats:
			raise ValueError("Participant seats are already configured")

		for seat in seats:
			self.addSeat(seat)

		self.configured = True