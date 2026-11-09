"""Le jeu de données respecte l'énoncé : 10 salles pour 1 700 places."""


def test_seed_rooms_total_capacity():
    from scripts.seed import ROOMS

    assert len(ROOMS) == 10
    assert sum(rows * per_row for _, rows, per_row in ROOMS) == 1700
