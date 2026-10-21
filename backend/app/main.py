from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import tools as tool_registry
from .core import ml_loader  # noqa: F401
from .core.config import get_settings
from .core.db import Base, engine, get_db
from .core.security import get_current_user
from .modules.agents.router import router as agents_router
from .modules.auth.router import router as auth_router
from .modules.carehub.router import router as carehub_router, seed_providers
from .modules.community.router import router as community_router, seed_channels
from .modules.clinical import tools as _clinical_tools  # noqa: F401  (registers the clinical tools)
from .modules.clinical.router import router as clinical_router
from .modules.buddy.router import router as buddy_router
from .modules.connect.router import router as connect_router
from .modules.doctor.router import router as doctor_router
from .modules.labs.router import router as labs_router
from .modules.notifications.router import router as notifications_router
from .modules.offline.router import router as offline_router
from .modules.reports.router import router as reports_router
from .modules.research.router import router as research_router
from .modules.rituals.router import router as rituals_router
from .modules.population import tools as _population_tools  # noqa: F401  (registers the population tools)
from .modules.population.router import router as population_router
from .modules.rx import tools as _rx_tools  # noqa: F401  (registers the Rx tools)
from .modules.rx.router import router as rx_router
from .modules.transplant import tools as _transplant_tools  # noqa: F401  (registers the transplant tools)
from .modules.transplant.router import router as transplant_router
from .modules.translate.router import router as translate_router
from .modules.whatsapp.router import router as whatsapp_router
from .modules.transplant.service import seed_hospitals
from . import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    from .core.db import SessionLocal

    with SessionLocal() as db:
        seed_channels(db)
        seed_providers(db)
        seed_hospitals(db)
    scheduler = None
    if get_settings().scheduler_enabled:
        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def start_scheduler():
    """Proactive helpers: run the agent checks every few minutes (lab due, rapid decline, urgent values...)."""
    from apscheduler.schedulers.background import BackgroundScheduler

    from .core.db import SessionLocal
    from .modules.agents.service import run_jobs

    def job():
        with SessionLocal() as db:
            run_jobs(db, None)

    sch = BackgroundScheduler(daemon=True)
    sch.add_job(job, "interval", minutes=get_settings().scheduler_minutes, id="agent-jobs", max_instances=1, coalesce=True)
    sch.start()
    return sch


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan,
              description="RenalSight backend: auth, labs, clinical ML tools. Local-only. Decision support, not a medical device.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")], allow_origin_regex=settings.cors_origin_regex,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "tools": len(tool_registry.REGISTRY)}


tools_router = APIRouter(prefix="/tools", tags=["tools"])


@tools_router.get("")
def list_tools(user=Depends(get_current_user)):
    """Tool catalogue for the signed-in role (the AI agents read this to know what they can call)."""
    return tool_registry.describe(user.role)


@tools_router.post("/{name}")
def call_tool(name: str, payload: dict | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return tool_registry.run_tool(name, tool_registry.Ctx(user=user, db=db), payload or {})


app.include_router(auth_router)
app.include_router(labs_router)
app.include_router(clinical_router)
app.include_router(rx_router)
app.include_router(doctor_router)
app.include_router(notifications_router)
app.include_router(buddy_router)
app.include_router(connect_router)
app.include_router(population_router)
app.include_router(rituals_router)
app.include_router(community_router)
app.include_router(carehub_router)
app.include_router(research_router)
app.include_router(offline_router)
app.include_router(reports_router)
app.include_router(agents_router)
app.include_router(transplant_router)
app.include_router(translate_router)
app.include_router(whatsapp_router)
app.include_router(tools_router)
