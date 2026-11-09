"""Point d'entrée de l'API La Grande Cinéma.

Documentation interactive (Swagger UI) : /docs — spécification OpenAPI : /openapi.json
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db import Base, engine
from app.routers import auth, bookings, catalog

settings = get_settings()

TAGS = [
    {"name": "Authentification", "description": "US01 — inscription, connexion JWT, profil."},
    {"name": "Catalogue", "description": "US02/US03 — films, séances et plan de salle (public)."},
    {"name": "Réservations", "description": "US04/US05/US06 — réserver, billet, annuler."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Création des tables si absentes (projet sans migrations : schéma maîtrisé dans docs/schema.sql).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="API de réservation de places en ligne pour le cinéma La Grande Cinéma.",
    openapi_tags=TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(bookings.router)


@app.get("/health", tags=["Supervision"])
def health() -> dict[str, str]:
    """Sonde de disponibilité utilisée par l'hébergeur."""
    return {"status": "ok"}
