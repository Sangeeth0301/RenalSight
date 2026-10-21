"""Single-service entrypoint for hosting: the API lives under /api and the built website is served from /.

    uvicorn app.deploy:root --host 0.0.0.0 --port $PORT

Same origin means no CORS and one public link. Build the website first (frontend/web: npm run build)."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .main import app as api

DIST = Path(os.getenv("FRONTEND_DIST") or Path(__file__).resolve().parents[2] / "frontend" / "web" / "dist")

root = FastAPI(title="RenalSight", lifespan=api.router.lifespan_context, docs_url=None, redoc_url=None, openapi_url=None)
root.mount("/api", api)


class SpaFiles(StaticFiles):
    """Static files with a fallback to index.html so deep links such as /doctor/patients/3 work after a refresh."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except Exception:                                     # unknown path: let the React router decide
            return FileResponse(DIST / "index.html")


if DIST.exists():
    root.mount("/", SpaFiles(directory=str(DIST), html=True), name="web")
else:
    @root.get("/")
    def missing():
        return JSONResponse({"detail": "Website not built. Run: cd frontend/web && npm run build"}, status_code=503)
