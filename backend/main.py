from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
from routers import subscriptions, analytics, uploads, data_generation, services, agent, voice
from modules.auth.router import router as auth_router
from modules.users.router import router as users_router
from modules.shops.router import router as shops_router
from modules.employees.router import router as employees_router
from modules.queues.router import router as queues_router
from modules.admin.router import router as admin_router
from scheduler import start_scheduler, stop_scheduler
import logging
import models # Force model registration
from websocket_manager import manager

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
    logger.info("Starting analytics scheduler...")
    await start_scheduler(run_at_hour=0, run_at_minute=30)  # Run at 00:30 daily
    logger.info("Application started")
    
    yield
    
    # Shutdown
    logger.info("Stopping analytics scheduler...")
    await stop_scheduler()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Universal Queue System API",
    description="API for managing queues for any service business",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(admin_router, prefix="/api", tags=["Admin"])

# Legacy/Shared routers (to be refactored)
app.include_router(uploads.router, prefix="/api", tags=["Uploads"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(data_generation.router, prefix="/api", tags=["Data Generation"])
app.include_router(services.router, prefix="/api", tags=["Services"])
app.include_router(agent.router, prefix="/api/agent", tags=["AI Agent"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])

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

@app.get("/")
async def root():
    return {"message": "Welcome to Universal Queue System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 