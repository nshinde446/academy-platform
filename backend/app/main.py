from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config.settings import get_settings
from app.core.logging.logger import setup_logging
from app.core.middleware.exception_handler import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.middleware.request_id import RequestIDMiddleware
from app.modules.academic.api.routes import router as academic_router
from app.modules.auth.api.routes import router as auth_router
from app.modules.audit.api.routes import router as audit_router
from app.modules.batch.api.routes import router as batch_router
from app.modules.classroom.api.routes import router as classroom_router
from app.modules.lectures.api.routes import router as lectures_router
from app.modules.student.api.routes import router as student_router
from app.modules.teacher.api.routes import router as teacher_router

settings = get_settings()
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
app.include_router(academic_router, prefix=settings.API_V1_PREFIX)
app.include_router(student_router, prefix=settings.API_V1_PREFIX)
app.include_router(teacher_router, prefix=settings.API_V1_PREFIX)
app.include_router(batch_router, prefix=settings.API_V1_PREFIX)
app.include_router(classroom_router, prefix=settings.API_V1_PREFIX)
app.include_router(lectures_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
