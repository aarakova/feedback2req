from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from feedback2req.api.materials import router as material_router
from feedback2req.api.routes import router
from feedback2req.api.security import RequestSecurity, error_response
from feedback2req.config import Settings
from feedback2req.errors import AppError
from feedback2req.identity.service import Identity
from feedback2req.persistence.database import make_database


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    engine, sessions = make_database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings, app.state.engine, app.state.sessions = settings, engine, sessions
    app.state.identity = Identity(settings)
    app.add_middleware(RequestSecurity, settings=settings)
    app.include_router(router)
    app.include_router(material_router)

    @app.exception_handler(AppError)
    async def application_error(request: Request, exc: AppError):
        return error_response(exc.status, exc.code, exc.message, request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error_response(
            422, "invalid_request", "Invalid request structure or values", request.state.request_id
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(
            exc.status_code, "http_error", "Request cannot be served", request.state.request_id
        )

    return app
