"""Point d'entrée de l'API La Grande Cinéma.

Documentation interactive (Swagger UI) : /docs — spécification OpenAPI : /openapi.json
"""

from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", tags=["Supervision"])
def health() -> dict[str, str]:
    """Sonde de disponibilité utilisée par l'hébergeur."""
    return {"status": "ok"}
