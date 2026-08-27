import time

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
	def utcNow(self) -> datetime:
		...

	def monotonic(self) -> float:
		...


class SystemClock:
	def utcNow(self) -> datetime:
		return datetime.now(timezone.utc)

	def monotonic(self) -> float:
		return time.monotonic()


SYSTEM_CLOCK: Clock = SystemClock()