"""What "now" is, in UTC.

Booking must start in the future, and a consultation can be completed only
after its start time. Those rules ask a ``Clock`` instead of calling
``datetime.now`` themselves, so a test can pass a ``FrozenClock`` set to a
chosen moment and check them without waiting.

Every value this module returns or accepts is timezone-aware UTC (rule R15).
"""

from datetime import UTC, datetime


def _as_utc(moment: datetime) -> datetime:
    """Reject a naive datetime and convert any other zone to UTC."""
    if moment.tzinfo is None:
        raise ValueError("Datetime values must be timezone-aware (UTC).")
    return moment.astimezone(UTC)


class Clock:
    """The live clock. ``now()`` is the current UTC moment."""

    def now(self) -> datetime:
        """The current moment as a timezone-aware UTC datetime."""
        return datetime.now(UTC)


class FrozenClock(Clock):
    """A clock stuck on one moment until a test moves it.

    Services depend on ``Clock``. A test constructs a ``FrozenClock`` and
    passes it in place of the live clock.
    """

    def __init__(self, moment: datetime) -> None:
        self._moment = _as_utc(moment)

    def now(self) -> datetime:
        """The pinned moment, unchanged until ``move_to``."""
        return self._moment

    def move_to(self, moment: datetime) -> None:
        """Report ``moment`` from the next ``now()`` call onward."""
        self._moment = _as_utc(moment)
