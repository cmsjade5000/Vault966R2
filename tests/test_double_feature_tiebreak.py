from api.services.double_feature import _shuffle_equal_scores


class _ReverseRandom:
    def shuffle(self, values):
        values.reverse()


def test_shuffle_equal_scores_shuffles_ties() -> None:
    ranked = [
        (2.0, 1),
        (2.0, 2),
        (1.5, 3),
        (1.5, 4),
        (1.5, 5),
        (1.0, 6),
    ]

    shuffled = _shuffle_equal_scores(ranked, _ReverseRandom())

    assert shuffled == [
        (2.0, 2),
        (2.0, 1),
        (1.5, 5),
        (1.5, 4),
        (1.5, 3),
        (1.0, 6),
    ]
