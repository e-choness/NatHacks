import numpy as np

from vision_pipeline import VisionPipeline


class _StubSettings:
    use_cloud = True
    face = True
    hands = False
    aruco = False


class _StubSession:
    routine_id = ""
    step_index = 0


class _StubHealth:
    fps = 0.0
    latency_ms = 0.0
    camera = "off"
    lighting = "unknown"


def _stub_broadcast(_msg):
    pass


def test_merge_cloud_landmarks_blends_values():
    vp = VisionPipeline(
        broadcast_fn=_stub_broadcast,
        settings=_StubSettings(),
        session=_StubSession(),
        health=_StubHealth(),
        camera_width=320,
        camera_height=240,
        camera_fps=1,
        camera_device=0,
        camera_enabled=False,
    )
    base = {"mouth_center": (0.5, 0.5)}
    cloud = {"mouth_center": (0.7, 0.3)}
    out = vp._merge_cloud_landmarks(base, cloud, confidence=0.6)
    assert "mouth_center" in out
    x, y = out["mouth_center"]
    assert 0.55 <= x <= 0.7
    assert 0.3 <= y <= 0.48
