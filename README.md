# La Grande Cinéma — API de réservation

API REST de l'application de réservation de places en ligne du cinéma **La Grande Cinéma**
(10 salles, 1 700 places), pensée pour absorber les pics d'affluence du festival de jazz.

- **Stack** : Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL (Neon), JWT, pytest
- **Documentation interactive (Swagger)** : `/docs` — spécification OpenAPI : `/openapi.json`
- **Front** : [grande-cinema-front](https://github.com/badr-tirari/grande-cinema-front)
- **Backlog** : projet Jira `CINE` (9 user stories, 3 epics)

## Fonctionnalités

| US | Fonctionnalité | Endpoints |
|---|---|---|
| CINE-4 | Inscription / connexion (JWT, rôles USER / ADMIN) | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| CINE-5 | Films et horaires des séances | `GET /api/movies`, `GET /api/movies/{id}`, `GET /api/showtimes` |
| CINE-6 | Places disponibles en temps réel | `GET /api/showtimes/{id}/seats` |
| CINE-7 | Réservation en ligne | `POST /api/bookings` |
| CINE-8 | Billet dématérialisé (code → QR code) | `GET /api/bookings/{id}` |
| CINE-9 | Mes réservations / annulation | `GET /api/bookings/me`, `POST /api/bookings/{id}/cancel` |
| CINE-10 | Gestion de la programmation (admin) | `POST/PATCH/DELETE /api/admin/movies`, `/api/admin/showtimes` |
| CINE-11 | Suivi des réservations (admin) | `GET /api/admin/bookings` |
| CINE-12 | Taux de remplissage et pics (admin) | `GET /api/admin/stats/occupancy` |

## Architecture

```
app/
├── core/        configuration (variables d'environnement) et sécurité (bcrypt, JWT, rôles)
├── routers/     couche HTTP : validation, codes de retour, documentation OpenAPI
├── services/    règles métier de la réservation, indépendantes de FastAPI
├── models.py    modèle de données SQLAlchemy
└── schemas.py   contrats d'entrée / sortie Pydantic
docs/            MCD (Mermaid + PNG) et script SQL PostgreSQL
scripts/seed.py  jeu de données de démonstration
tests/           tests unitaires et d'API (pytest)
```

Modèle de données : voir [`docs/mcd.png`](docs/mcd.png) et [`docs/schema.sql`](docs/schema.sql).
La contrainte `UNIQUE (showtime_id, seat_id)` de `booked_seats` empêche, au niveau de la base,
qu'une même place soit vendue deux fois pour une séance, même en cas de requêtes simultanées.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
python -m scripts.seed
uvicorn app.main:app --reload
```

Puis ouvrir http://localhost:8000/docs.

## Qualité

```bash
ruff check .                                  # lint
pytest --cov=app --cov-report=term-missing    # tests + couverture
```

La CI GitHub Actions exécute lint, tests (couverture minimale 80 %) et l'analyse SonarCloud
à chaque push et merge request sur `main` et `develop`.

## Déploiement (offres gratuites, sans carte bancaire)

| Composant | Hébergeur |
|---|---|
| API | Render (Web Service, `render.yaml`) |
| Base PostgreSQL | Neon |
| Front React | Vercel |

Conventions Git : voir [CONTRIBUTING.md](CONTRIBUTING.md).
