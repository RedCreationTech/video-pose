from video_pose.homography import HomographyCorrespondence, fit_homography


def test_fit_homography_recovers_scale_transform() -> None:
    points = [
        HomographyCorrespondence(
            image={"x": 0, "y": 0},
            world={"x": 0, "y": 0},
        ),
        HomographyCorrespondence(
            image={"x": 100, "y": 0},
            world={"x": 200, "y": 0},
        ),
        HomographyCorrespondence(
            image={"x": 100, "y": 50},
            world={"x": 200, "y": 100},
        ),
        HomographyCorrespondence(
            image={"x": 0, "y": 50},
            world={"x": 0, "y": 100},
        ),
        HomographyCorrespondence(
            image={"x": 50, "y": 25},
            world={"x": 100, "y": 50},
        ),
    ]
    result = fit_homography(points)
    assert result.rmse < 1e-6
    assert abs(result.homography[0][0] - 2.0) < 1e-6
    assert abs(result.homography[1][1] - 2.0) < 1e-6
