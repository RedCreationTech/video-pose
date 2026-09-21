from video_pose.model_pool import PersistentModelPool


class FakeDetector:
    def __init__(self, *, fail=False):
        self.load_calls = 0
        self.detect_calls = 0
        self.fail = fail

    def load(self):
        self.load_calls += 1

    def detect(self, _image):
        self.detect_calls += 1
        if self.fail:
            raise RuntimeError("detector failed")
        return []


class FakePose:
    def __init__(self):
        self.load_calls = 0
        self.infer_calls = 0

    def load(self):
        self.load_calls += 1

    def infer(self, _image, persons):
        self.infer_calls += 1
        assert len(persons) == 1
        assert persons[0].entity_id == "warmup-person"
        return [object()]


def test_model_warmup_executes_detector_and_pose_once() -> None:
    detector = FakeDetector()
    pose = FakePose()
    pool = PersistentModelPool(
        detector=detector,
        pose_estimator=pose,
        warmup_enabled=True,
        warmup_image_size=128,
    )
    pool.load()
    first = pool.warmup()
    second = pool.warmup()

    assert first.status == "PASS"
    assert first.latency_ms is not None
    assert first.pose_result_count == 1
    assert second.status == "PASS"
    assert detector.detect_calls == 1
    assert pose.infer_calls == 1


def test_model_warmup_failure_is_observable_without_raise() -> None:
    pool = PersistentModelPool(
        detector=FakeDetector(fail=True),
        pose_estimator=None,
        warmup_enabled=True,
        warmup_image_size=128,
    )
    pool.load()
    result = pool.warmup()
    assert result.status == "FAIL"
    assert result.error_type == "RuntimeError"
    assert pool.warmup_health().status == "FAIL"
