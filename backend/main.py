from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
from routers import users, auth, shops, queues, subscriptions, analytics, uploads, employees, data_generation, services
from scheduler import start_scheduler, stop_scheduler
import logging

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
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(shops.router, prefix="/api/shops", tags=["Shops"])
app.include_router(employees.router, prefix="/api", tags=["Employees"])
app.include_router(queues.router, prefix="/api/queues", tags=["Queues"])
app.include_router(uploads.router, prefix="/api", tags=["Uploads"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(data_generation.router, prefix="/api", tags=["Data Generation"])
app.include_router(services.router, prefix="/api", tags=["Services"])

@app.get("/")
async def root():
    return {"message": "Welcome to Universal Queue System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 