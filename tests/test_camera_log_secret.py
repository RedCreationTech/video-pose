from video_pose.live_gateway import OpenCVLiveCamera


class FakeCapture:
    def isOpened(self):
        return False

    def release(self):
        pass


class FakeCV2:
    def VideoCapture(self, _uri):
        return FakeCapture()


def test_camera_open_error_does_not_expose_rtsp_uri() -> None:
    camera = OpenCVLiveCamera(
        "front",
        "rtsp://user:password@camera.local/private",
    )
    camera._cv2_module = FakeCV2()
    try:
        camera.open()
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("camera.open() should fail")

    assert "front" in message
    assert "password" not in message
    assert "rtsp://" not in message
