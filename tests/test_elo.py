import pytest

from hivesim.elo import expected_score, update_ratings


def test_expected_score_equal_ratings_is_half():
    assert expected_score(1200, 1200) == pytest.approx(0.5)


def test_expected_scores_are_complementary():
    a_vs_b = expected_score(1400, 1200)
    b_vs_a = expected_score(1200, 1400)
    assert a_vs_b + b_vs_a == pytest.approx(1.0)


def test_update_ratings_white_win_from_equal_ratings():
    white_new, black_new = update_ratings(1200, 1200, winner="white")
    assert white_new == pytest.approx(1216.0)
    assert black_new == pytest.approx(1184.0)


def test_update_ratings_draw_moves_toward_each_other():
    white_new, black_new = update_ratings(1400, 1200, winner=None)
    assert white_new < 1400
    assert black_new > 1200


def test_update_ratings_invalid_winner_raises():
    with pytest.raises(ValueError):
        update_ratings(1200, 1200, winner="invalid")
