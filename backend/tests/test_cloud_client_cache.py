import time

from cloud_vision import CloudVisionClient


def test_cache_key_stability():
    import numpy as np
    import cv2
    client = CloudVisionClient()
    # Build synthetic small ROI
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    cv2.circle(img, (32, 32), 10, (255, 255, 255), -1)
    key1 = client._cache_key(img)
    key2 = client._cache_key(img)
    assert key1 == key2


def test_rate_limit_reservation():
    client = CloudVisionClient(rps=2, min_interval_ms=0)
    now = time.time()
    now_ns = time.time_ns()
    # Reserve two slots quickly
    assert client._reserve_slot_locked(now, now_ns) is True
    assert client._reserve_slot_locked(now, now_ns) is True
    # Third should fail within same second
    assert client._reserve_slot_locked(now, now_ns) is False
