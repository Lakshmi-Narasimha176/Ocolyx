from __future__ import annotations

import numpy as np

from src.ocolyx.blink_detector import _euclidean_distance, eye_aspect_ratio


def test_euclidean_distance_matches_pythagorean_theorem() -> None:
    point_a = np.array([0.0, 0.0])
    point_b = np.array([3.0, 4.0])

    assert _euclidean_distance(point_a, point_b) == 5.0


def test_eye_aspect_ratio_matches_manual_formula() -> None:
    eye_points = np.array(
        [
            [0.0, 0.0],
            [1.0, 3.0],
            [2.0, 3.0],
            [4.0, 0.0],
            [2.0, -3.0],
            [1.0, -3.0],
        ],
        dtype=float,
    )

    vertical_1 = 6.0
    vertical_2 = 6.0
    horizontal = 4.0
    expected = (vertical_1 + vertical_2) / (2.0 * horizontal)

    assert eye_aspect_ratio(eye_points) == expected


def test_eye_aspect_ratio_returns_zero_when_horizontal_distance_is_zero() -> None:
    eye_points = np.array(
        [
            [0.0, 0.0],
            [0.0, 2.0],
            [0.0, 3.0],
            [0.0, 0.0],
            [0.0, -3.0],
            [0.0, -2.0],
        ],
        dtype=float,
    )

    assert eye_aspect_ratio(eye_points) == 0.0
