from video_pose.model_pool import PersistentModelPool


class FakeModel:
    def __init__(self) -> None:
        self.load_calls = 0

    def load(self) -> None:
        self.load_calls += 1


def test_model_pool_loads_heavy_models_only_once() -> None:
    detector = FakeModel()
    pose = FakeModel()
    pool = PersistentModelPool(
        detector=detector,
        pose_estimator=pose,
    )

    pool.load()
    pool.load()

    assert pool.loaded is True
    assert detector.load_calls == 1
    assert pose.load_calls == 1
