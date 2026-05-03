from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import re as _re
import uvicorn
from contextlib import asynccontextmanager
from routers import subscriptions, analytics, uploads, data_generation, services, agent, agent_v2, voice, registration, tenants, payments, llm_settings
from modules.auth.router import router as auth_router
from modules.users.router import router as users_router
from modules.shops.router import router as shops_router
from modules.employees.router import router as employees_router
from modules.queues.router import router as queues_router
from modules.appointments.router import router as appointments_router
from modules.admin.router import router as admin_router
from modules.testing.routes import router as testing_router
from modules.feedback.router import router as feedback_router
from scheduler import start_scheduler, stop_scheduler
from audit_logger import start_worker as _audit_start, stop_worker as _audit_stop
from telegram_polling import start_polling as _telegram_polling_start, stop_polling as _telegram_polling_stop
import logging
import models # Force model registration
from websocket_manager import manager
import agent_logic  # Force eager loading of sentence-transformer model at startup  # noqa: F401
from database import set_tenant_for_request, SessionLocal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup

    # Ensure all SQLAlchemy model tables exist (idempotent — safe on every restart).
    # This replaces the init-database K8s initContainer so the image is self-contained.
    try:
        from database import engine, Base
        import models  # noqa: F401 — registers all mapped classes with Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema ready.")
    except Exception as _db_err:
        logger.warning(f"Database schema initialization warning: {_db_err}")

    logger.info("Starting analytics scheduler...")
    await start_scheduler(run_at_hour=0, run_at_minute=30)  # Run at 00:30 daily
    
    # Ensure chat_feedback table exists
    try:
        from database import engine
        from modules.feedback.models import ChatFeedback
        import os as _mkdir_os
        _mkdir_os.makedirs("static/uploads/feedback", exist_ok=True)
        ChatFeedback.__table__.create(bind=engine, checkfirst=True)
        logger.info("chat_feedback table ready.")
    except Exception as _fb_err:
        logger.warning(f"chat_feedback table setup warning: {_fb_err}")

    # Setup LangGraph checkpoint tables (Phase 1)
    try:
        logger.info("Setting up LangGraph checkpoint tables...")
        from agents.checkpoints import setup_checkpoint_tables
        await setup_checkpoint_tables()
        logger.info("LangGraph checkpoint tables ready.")
    except Exception as e:
        logger.warning(f"LangGraph checkpoint setup warning: {e}")
    
    # Pre-warm the semantic cache (loads sentence-transformer model) before serving requests.
    # This avoids a 60-90s stall on the first chat request after a pod restart.
    try:
        import asyncio
        import concurrent.futures
        logger.info("Pre-warming semantic cache (loading sentence-transformer model)...")
        loop = asyncio.get_event_loop()
        def _prewarm():
            from agent_logic import semantic_cache  # noqa: triggers model load
            return True
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, _prewarm)
        logger.info("Semantic cache pre-warm complete.")
    except Exception as e:
        logger.warning(f"Semantic cache pre-warm failed (non-fatal): {e}")
    
    # Start async audit writer
    _audit_start()
    logger.info("Audit logger started")

    try:
        await _telegram_polling_start()
    except Exception as _telegram_polling_err:
        logger.warning(f"Telegram polling startup warning: {_telegram_polling_err}")

    logger.info("Application started")
    
    yield
    
    # Shutdown
    logger.info("Stopping audit logger...")
    await _audit_stop()
    logger.info("Stopping Telegram polling...")
    await _telegram_polling_stop()
    logger.info("Stopping analytics scheduler...")
    await stop_scheduler()
    logger.info("Application shutdown complete")



app = FastAPI(
    title="Universal Queue System API",
    description="API for managing queues for any service business",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",  # Moved Swagger UI to /api/docs
    openapi_url="/api/openapi.json"  # Moved OpenAPI schema
)

# Configure CORS
import os
allowed_origins = [
    "http://localhost:3000",
    "http://192.168.1.15:3000",
    "https://zeroqwait.com",
    "https://www.zeroqwait.com",
    "http://192.168.2.88.nip.io",
    "http://*.192.168.2.88.nip.io",  # Support all shop subdomains
]

# Allow custom frontend URL from environment variable
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in allowed_origins:
    allowed_origins.append(frontend_url)
    # Also add subdomain versions
    if "nip.io" in frontend_url or "localhost" not in frontend_url:
        allowed_origins.append(f"http://*.{frontend_url.replace('http://', '')}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Docs no-cache middleware ─────────────────────────────────────────
# Prevent browsers from caching .md files so docs updates are always fresh.
class DocsNoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/docs/") and request.url.path.endswith(".md"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(DocsNoCacheMiddleware)


# ── Tenant middleware ───────────────────────────────────────────────
# Extracts shop_id from the request path, looks up the shop's tenant
# schema, and sets a ContextVar so every SessionLocal() created during
# the request automatically gets the correct search_path.

class TenantMiddleware(BaseHTTPMiddleware):
    _SHOP_ID_PATTERNS = [
        _re.compile(r'/api/queues/shop/(\d+)'),
        _re.compile(r'/api/shops/(\d+)'),
        _re.compile(r'/api/employees/shops/(\d+)'),
        _re.compile(r'/api/analytics/(?:daily/|peak-hours/|archive/stats/|services/|revenue/monthly-by-service/)?(\d+)'),
        _re.compile(r'/api/services/shops/(\d+)'),
        _re.compile(r'/api/appointments/shop/(\d+)'),
    ]

    async def dispatch(self, request: Request, call_next):
        shop_id = self._extract_shop_id(request.url.path)
        if shop_id:
            db = SessionLocal()
            try:
                from sqlalchemy import text
                row = db.execute(
                    text("SELECT tenant_schema FROM shops WHERE id = :sid"),
                    {"sid": shop_id}
                ).fetchone()
                if row and row[0]:
                    set_tenant_for_request(row[0])
            finally:
                db.close()
        try:
            response = await call_next(request)
        finally:
            set_tenant_for_request(None)
        return response

    @staticmethod
    def _extract_shop_id(path: str):
        for pattern in TenantMiddleware._SHOP_ID_PATTERNS:
            m = pattern.search(path)
            if m:
                return int(m.group(1))
        return None

app.add_middleware(TenantMiddleware)

from fastapi.staticfiles import StaticFiles
import os

# Create static directory if it doesn't exist
if not os.path.exists("static/uploads"):
    os.makedirs("static/uploads")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
# Modular routers
app.include_router(auth_router, prefix="/api", tags=["Authentication"])
app.include_router(users_router, prefix="/api", tags=["Users"])
app.include_router(shops_router, prefix="/api/shops", tags=["Shops"])
app.include_router(employees_router, prefix="/api", tags=["Employees"])
app.include_router(queues_router, prefix="/api/queues", tags=["Queues"])
app.include_router(appointments_router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])

# Legacy/Shared routers (to be refactored)
app.include_router(uploads.router, prefix="/api", tags=["Uploads"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(data_generation.router, prefix="/api", tags=["Data Generation"])
app.include_router(services.router, prefix="/api", tags=["Services"])
app.include_router(llm_settings.router, prefix="/api", tags=["LLM Settings"])
app.include_router(agent.router, prefix="/api/agent", tags=["AI Agent"])
app.include_router(agent_v2.router, prefix="", tags=["AI Agent v2"])
app.include_router(registration.router, prefix="/api/agent/registration", tags=["Registration"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(tenants.router, prefix="/api", tags=["Tenants"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(testing_router, tags=["Testing Feedback"])
app.include_router(feedback_router, prefix="/api", tags=["Chat Feedback"])

# Serve Docsify-based documentation site at /docs
import os as _os
_docs_site_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "docs_site")
app.mount("/docs", StaticFiles(directory=_docs_site_dir, html=True), name="docs")

@app.websocket("/ws/{shop_id}")
async def websocket_endpoint(websocket: WebSocket, shop_id: str):
    await manager.connect(websocket, shop_id)
    try:
        while True:
            # We just keep the connection open to push updates
            # Verify client is still there
            data = await websocket.receive_text()
            # Optional: handle client messages if needed
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        manager.disconnect(websocket, shop_id)


@app.websocket("/api/ws/{shop_id}")
async def api_websocket_endpoint(websocket: WebSocket, shop_id: str):
    await manager.connect(websocket, shop_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        manager.disconnect(websocket, shop_id)

@app.get("/")
async def root():
    return {"message": "Welcome to Universal Queue System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 
