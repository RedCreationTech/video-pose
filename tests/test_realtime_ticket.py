import time

import pytest

from video_pose.auth import (
    AuthPrincipal,
    AuthenticationError,
    Permission,
    Role,
)
from video_pose.realtime_ticket import RealtimeTicketManager


def _principal() -> AuthPrincipal:
    return AuthPrincipal(
        subject="operator-1",
        role=Role.OPERATOR,
        permissions={Permission.REALTIME_READ},
    )


def test_realtime_ticket_is_one_time() -> None:
    manager = RealtimeTicketManager(ttl_seconds=30)
    issued = manager.issue(_principal())
    assert manager.outstanding() == 1

    principal = manager.consume(issued.ticket)
    assert principal.subject == "operator-1"
    assert manager.outstanding() == 0

    with pytest.raises(AuthenticationError):
        manager.consume(issued.ticket)


def test_realtime_ticket_expires() -> None:
    manager = RealtimeTicketManager(ttl_seconds=1)
    issued = manager.issue(_principal())
    time.sleep(1.05)
    with pytest.raises(AuthenticationError):
        manager.consume(issued.ticket)
