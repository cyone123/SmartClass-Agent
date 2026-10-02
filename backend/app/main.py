import asyncio
import sys

from fastapi import FastAPI, Request, status
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.file import router as file_router
from app.api.memory import router as memory_router
from app.api.plan import router as plan_router
from app.api.session import router as session_router
from app.config import get_memory_reflection_worker_enabled, get_otel_environment
from app.core.agent import create_agent_runtime
from app.core.chat_run_events import ChatRunEventStoreError, ChatRunRedis
from app.core.chat_runs import ChatRunManager
from app.core.file_ingestion import FileIngestionRuntime
from app.core.memory_worker import MemoryReflectionWorker
from app.core.model_access import initialize as initialize_model_access
from app.core.model_access import shutdown as shutdown_model_access
from app.core.observability import RunContext, get_observation_sink, log_observation
from app.core.observability_bootstrap import configure_external_observability
from app.core.rag import create_rag_runtime
from app.core.skills import create_skill_registry
from app.core.speech import create_speech_runtime
from app.core.video_transcribe import create_video_transcription_runtime
from app.dependencies.db import close_db_resources, init_db

if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _start_memory_reflection_worker(memory_store):
    if not get_memory_reflection_worker_enabled():
        return None
    try:
        worker = MemoryReflectionWorker(memory_store)
        await worker.start()
        return worker
    except Exception as exc:
        log_observation(
            "memory.worker.start_failed",
            context=RunContext(run_id="startup", agent_name="memory_worker"),
            sink=get_observation_sink(),
            status="failed",
            fields={"error_category": "startup_error", "error_type": exc.__class__.__name__},
        )
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent_runtime = None
    chat_run_manager = None
    file_ingestion_runtime = None
    rag_runtime = None
    skill_registry = None
    speech_runtime = None
    video_transcription_runtime = None
    chat_run_redis = None
    memory_reflection_worker = None
    try:
        initialize_model_access()
        await init_db()
        chat_run_redis = ChatRunRedis.from_config(environment=get_otel_environment())
        app.state.chat_run_redis = chat_run_redis
        try:
            await chat_run_redis.start()
        except ChatRunEventStoreError:
            pass
        skill_registry = create_skill_registry()
        app.state.skill_registry = skill_registry
        rag_runtime = await create_rag_runtime()
        app.state.rag_runtime = rag_runtime
        speech_runtime = create_speech_runtime()
        app.state.speech_runtime = speech_runtime
        video_transcription_runtime = create_video_transcription_runtime(
            speech_runtime=speech_runtime,
        )
        app.state.video_transcription_runtime = video_transcription_runtime
        file_ingestion_runtime = FileIngestionRuntime(rag_runtime)
        await file_ingestion_runtime.start()
        app.state.file_ingestion_runtime = file_ingestion_runtime
        agent_runtime = await create_agent_runtime(
            rag_runtime,
            skill_registry=skill_registry,
            video_transcription_runtime=video_transcription_runtime,
        )
        app.state.agent_runtime = agent_runtime
        memory_reflection_worker = await _start_memory_reflection_worker(agent_runtime.memory_store)
        if memory_reflection_worker is not None:
            app.state.memory_reflection_worker = memory_reflection_worker
        chat_run_manager = ChatRunManager(agent_runtime, chat_run_redis)
        await chat_run_manager.start()
        app.state.chat_run_manager = chat_run_manager
        yield
    finally:
        if chat_run_manager is not None:
            await chat_run_manager.stop()
        if memory_reflection_worker is not None:
            await memory_reflection_worker.stop()
        if agent_runtime is not None:
            await agent_runtime.close()
        if file_ingestion_runtime is not None:
            await file_ingestion_runtime.stop()
        if rag_runtime is not None:
            await rag_runtime.close()
        if chat_run_redis is not None:
            await chat_run_redis.close()
        try:
            await close_db_resources()
        finally:
            await shutdown_model_access()


app = FastAPI(lifespan=lifespan)
configure_external_observability(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check(request: Request):
    event_store = getattr(request.app.state, "chat_run_redis", None)
    if event_store is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "dependencies": {"redis": "uninitialized"}},
        )
    try:
        await event_store.ensure_ready()
    except ChatRunEventStoreError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "dependencies": {"redis": "unavailable"}},
        )
    return {"status": "ready", "dependencies": {"redis": "healthy"}}


app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(file_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(plan_router, prefix="/api")
app.include_router(session_router, prefix="/api")
