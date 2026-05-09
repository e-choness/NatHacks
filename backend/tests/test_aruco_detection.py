import numpy as np
import cv2
import pytest
from ar_overlay import detect_markers


def test_detect_single_marker():
    if not hasattr(cv2, 'aruco'):
        pytest.skip('cv2.aruco not available')
    aruco = cv2.aruco
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_5X5_250)
    marker_id = 23
    size = 200
    marker = None
    # Newer API
    if hasattr(aruco, 'generateImageMarker'):
        marker = aruco.generateImageMarker(dictionary, marker_id, size)
    elif hasattr(aruco, 'drawMarker'):
        marker = aruco.drawMarker(dictionary, marker_id, size)
    else:
        pytest.skip('No ArUco marker generation API available')
    canvas = 255 * np.ones((400, 400), dtype=np.uint8)
    canvas[100:100+size, 100:100+size] = marker
    bgr = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    results = detect_markers(bgr)
    assert any(r['id'] == marker_id for r in results), 'Marker 23 not detected'
    for r in results:
        if r['id'] == marker_id:
            cx = r['center_px']['x']
            cy = r['center_px']['y']
            assert 100 < cx < 300 and 100 < cy < 300, 'Center out of expected range'
            break
