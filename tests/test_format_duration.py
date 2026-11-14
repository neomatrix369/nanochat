"""
Author: nanochat Modal slice (Claude)
Created: 2026-11-14
Scope: nanochat.common.format_duration, the 'H h M m S s' form used in training logs.
"""

import pytest

from nanochat.common import format_duration


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0 h 0 m 0 s"),
        (42, "0 h 0 m 42 s"),
        (125, "0 h 2 m 5 s"),
        (3725, "1 h 2 m 5 s"),
        (489.8 * 60, "8 h 9 m 48 s"),
        (-5, "0 h 0 m 0 s"),
    ],
)
def test_format_duration_shows_hours_minutes_seconds(seconds: float, expected: str) -> None:
    """
    Scenario: durations of seconds, minutes, hours, and a long ETA are shown as H h M m S s.
    Slice: readable time in training logs.
    """
    # ### Given / ### When
    text = format_duration(seconds)

    # ### Then
    assert text == expected
