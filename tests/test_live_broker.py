from video_pose.live_broker import LiveEventBroker


def test_empty_broker_has_no_latest_event() -> None:
    broker = LiveEventBroker()
    assert broker.latest() is None
    assert broker.wait_next(0, timeout_s=0.001) is None
