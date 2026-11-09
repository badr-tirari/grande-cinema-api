"""Jeu de données de démonstration : 10 salles (1 700 places), films, séances, comptes.

Usage : python -m scripts.seed            (n'écrase rien si des données existent)
        python -m scripts.seed --reset    (vide et recharge la base)

Les mots de passe des comptes de démo sont lus dans SEED_ADMIN_PASSWORD et
SEED_USER_PASSWORD (valeurs par défaut uniquement pour le développement local).
"""

import os
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Movie, Role, Room, Showtime, User
from app.services.booking import create_room_with_seats, ends_at_for

# 10 salles modulables, capacité totale 1 700 places (énoncé).
ROOMS = [
    ("Salle 1", 15, 20),  # 300
    ("Salle 2", 12, 20),  # 240
    ("Salle 3", 10, 20),  # 200
    ("Salle 4", 10, 18),  # 180
    ("Salle 5", 10, 16),  # 160
    ("Salle 6", 10, 15),  # 150
    ("Salle 7", 10, 14),  # 140
    ("Salle 8", 10, 12),  # 120
    ("Salle 9", 10, 11),  # 110
    ("Salle 10", 10, 10),  # 100
]

MOVIES = [
    ("Blue Note Nights", "Documentaire sur les grandes heures du jazz moderne.", "Documentaire", 95),
    ("Le Dernier Train pour Sète", "Comédie dramatique sur la route du festival.", "Comédie", 108),
    ("Orbite", "Une mission spatiale tourne mal au-dessus de la Méditerranée.", "Science-fiction", 132),
    ("Les Gardiens du Phare", "Film d'animation familial.", "Animation", 88),
    ("Contretemps", "Thriller musical dans les coulisses d'un club de jazz.", "Thriller", 117),
    ("Saison Sèche", "Drame rural sur la gestion de l'eau.", "Drame", 101),
]

SESSIONS = [time(14, 0), time(17, 30), time(20, 45)]  # heure locale du cinéma
PARIS = ZoneInfo("Europe/Paris")


def seed(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if db.scalars(select(Room)).first() is not None:
            print("Base déjà initialisée - rien à faire (utilisez --reset pour recharger).")
            return

        rooms = [create_room_with_seats(db, name, rows, per_row) for name, rows, per_row in ROOMS]
        if sum(r.capacity for r in rooms) != 1700:
            raise RuntimeError("La capacité totale doit être de 1 700 places (énoncé)")

        movies = [Movie(title=t, description=d, genre=g, duration_min=m) for t, d, g, m in MOVIES]
        db.add_all(movies)
        db.flush()

        today = datetime.now(PARIS).date()
        for day_offset in range(1, 8):
            day = today + timedelta(days=day_offset)
            for i, room in enumerate(rooms[:6]):
                movie = movies[(i + day_offset) % len(movies)]
                for slot in SESSIONS:
                    starts = datetime.combine(day, slot, tzinfo=PARIS)
                    weekend = day.weekday() >= 5
                    db.add(
                        Showtime(
                            movie_id=movie.id,
                            room_id=room.id,
                            starts_at=starts,
                            ends_at=ends_at_for(starts, movie.duration_min),
                            price_cents=1150 if weekend else 990,
                        )
                    )

        db.add_all(
            [
                User(
                    email="admin@grandecinema.fr",
                    full_name="Administration La Grande Cinéma",
                    hashed_password=hash_password(os.getenv("SEED_ADMIN_PASSWORD", "Admin-Cinema-2026")),
                    role=Role.ADMIN,
                ),
                User(
                    email="spectateur@grandecinema.fr",
                    full_name="Spectateur Démo",
                    hashed_password=hash_password(os.getenv("SEED_USER_PASSWORD", "Spectateur-2026")),
                    role=Role.USER,
                ),
            ]
        )
        db.commit()
        print(
            "Données de démonstration chargées : 10 salles / 1 700 places, 6 films, 126 séances, 2 comptes."
        )


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
