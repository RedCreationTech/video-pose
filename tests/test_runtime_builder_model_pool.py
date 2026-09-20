from video_pose.model_pool import PersistentModelPool
from video_pose.runtime_builder import build_analysis_pipeline
from video_pose.runtime_config import load_analysis_config


class FakeDetector:
    model_name = "fake"
    model_version = "1"

    def load(self) -> None:
        pass

    def detect(self, _image):
        return []


class FakeFrameLoader:
    def load(self, _ref):
        raise AssertionError("not used")


def test_two_session_pipelines_reuse_same_detector_instance() -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    detector = FakeDetector()
    pool = PersistentModelPool(
        detector=detector,
        pose_estimator=None,
    )

    first = build_analysis_pipeline(
        loaded,
        session_id="s1",
        frame_loader=FakeFrameLoader(),
        model_pool=pool,
    )
    second = build_analysis_pipeline(
        loaded,
        session_id="s2",
        frame_loader=FakeFrameLoader(),
        model_pool=pool,
    )

    first_model = first.perception.model
    second_model = second.perception.model
    assert first_model.detector is detector
    assert second_model.detector is detector
    assert first_model is not second_model
