from video_pose.adapters.ultralytics_yolo import UltralyticsDetector


class FakeTensor:
    def __init__(self, value: list[object]) -> None:
        self.value = value

    def cpu(self) -> "FakeTensor":
        return self

    def tolist(self) -> list[object]:
        return self.value


class FakeBoxes:
    xyxy = FakeTensor([[10.0, 20.0, 110.0, 220.0]])
    conf = FakeTensor([0.94])
    cls = FakeTensor([0.0])


class FakeResult:
    boxes = FakeBoxes()
    names = {0: "person"}


class FakeModel:
    def predict(self, **_kwargs: object) -> list[FakeResult]:
        return [FakeResult()]


def test_ultralytics_adapter_normalizes_boxes() -> None:
    detector = UltralyticsDetector(
        "fake.pt",
        model=FakeModel(),
        allowed_classes={"person"},
    )
    output = detector.detect("fake-image")
    assert len(output) == 1
    assert output[0].class_name == "person"
    assert output[0].confidence == 0.94
    assert output[0].bbox.x2 == 110.0
