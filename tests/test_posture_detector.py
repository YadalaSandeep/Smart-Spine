import pytest
import numpy as np
from posture_detector import PostureDetector

def test_vertical_angle():
    a = np.array([0, 0])
    b = np.array([0, 1])
    # Vector (0,1) is downward vertical
    assert PostureDetector._vertical_angle(a, b) == 0.0

    a = np.array([0, 0])
    b = np.array([1, 0])
    # Vector (1,0) is horizontal
    assert PostureDetector._vertical_angle(a, b) == 90.0

    a = np.array([0, 0])
    b = np.array([0, -1])
    # Vector (0,-1) is upward vertical
    assert PostureDetector._vertical_angle(a, b) == 180.0

def test_to_px():
    class MockLM:
        def __init__(self, x, y):
            self.x = x
            self.y = y
    
    lm = MockLM(0.5, 0.5)
    px = PostureDetector._to_px(lm, 480, 640)
    assert np.array_equal(px, [320, 240])
