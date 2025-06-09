import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
import httpx
import os
from dotenv import load_dotenv
from vexa_client.client import VexaClient
from core.database import init_db
from routers import bots, admin, webhooks, transcripts

load_dotenv()

# Configuration from environment variables
VEXA_INFRA_API_URL = os.getenv("VEXA_INFRA_API_URL", "https://gateway.dev.vexa.ai")
VEXA_INFRA_API_KEY = os.getenv("VEXA_INFRA_API_KEY")

# Security Schemes
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_api_key_scheme = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)

app = FastAPI(
    title="Vexa Retailer API",
    description="The Vexa Retailer Service.",
    version="3.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Service Clients and DB Initialization ---
@app.on_event("startup")
async def startup_event():
    app.state.http_client = httpx.AsyncClient()
    if not VEXA_INFRA_API_KEY:
        raise RuntimeError("VEXA_INFRA_API_KEY must be set in the environment.")
    app.state.infra_client = VexaClient(
        base_url=VEXA_INFRA_API_URL,
        api_key=VEXA_INFRA_API_KEY
    )
    await init_db()

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.http_client.aclose()


# --- Authentication ---
# The get_user_from_api_key dependency is now imported from core/auth.py
# and directly used in the routers that need it.


# --- Root Endpoint ---
@app.get("/", tags=["General"])
def root():
    return {"message": "Welcome to the Vexa Retailer API"}

# --- Include Routers ---
app.include_router(bots.router)
app.include_router(admin.admin_router)
app.include_router(admin.user_router)
app.include_router(webhooks.router)
app.include_router(transcripts.router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)