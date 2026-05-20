"""ELO rating calculations for Hive bot matches."""

from __future__ import annotations

DEFAULT_K: float = 32.0
DEFAULT_RATING: float = 1200.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """Return P(A beats B) as a probability in [0, 1]."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_ratings(
    rating_a: float,
    rating_b: float,
    winner: str | None,
    k: float = DEFAULT_K,
) -> tuple[float, float]:
    """Return updated ELO ratings for white(A) and black(B).

    `winner` must be one of:
    - \"white\": white/A wins
    - \"black\": black/B wins
    - None: draw
    """
    expected_a = expected_score(rating_a, rating_b)
    expected_b = expected_score(rating_b, rating_a)

    if winner == "white":
        actual_a, actual_b = 1.0, 0.0
    elif winner == "black":
        actual_a, actual_b = 0.0, 1.0
    elif winner is None:
        actual_a, actual_b = 0.5, 0.5
    else:
        raise ValueError("winner must be 'white', 'black', or None")

    new_a = rating_a + k * (actual_a - expected_a)
    new_b = rating_b + k * (actual_b - expected_b)
    return new_a, new_b
