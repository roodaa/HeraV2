"""Application FastAPI principale pour HERA V2."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.routes import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    # Startup
    print(f"🚀 Démarrage de {settings.app_name} v{settings.app_version}")
    print(f"📊 Mode: {settings.environment}")
    print(f"🔐 Provider d'authentification: {settings.auth_provider}")

    yield

    # Shutdown
    print("👋 Arrêt de l'application")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API Backend pour l'application de comptabilité carbone HERA V2",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routes API
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Route racine."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Vérification de santé de l'API."""
    return {"status": "healthy"}
