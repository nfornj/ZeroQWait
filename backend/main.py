from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from routers import users, auth, shops, queues, subscriptions, analytics, uploads, employees

app = FastAPI(
    title="Universal Queue System API",
    description="API for managing queues for any service business",
    version="1.0.0"
)

# Configure CORS
import os
allowed_origins = [
    "http://localhost:3000",
    "https://zeroqwait.com",
    "https://www.zeroqwait.com",
]

# Allow custom frontend URL from environment variable
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in allowed_origins:
    allowed_origins.append(frontend_url)

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

@app.get("/")
async def root():
    return {"message": "Welcome to Universal Queue System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 