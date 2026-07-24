"""
OIC NetRadar - Enterprise Network Monitoring System
Main Application Entry Point
"""

import os
import sys
import asyncio
import logging

# ============================================================================
# Windows Event Loop Policy
# ============================================================================
# On Windows, asyncio.create_subprocess_exec() (used by DiagnosticEngine for
# ping/traceroute) requires the ProactorEventLoop. Uvicorn/some libraries can
# default to SelectorEventLoop, which raises NotImplementedError (with an
# EMPTY message) for subprocess calls. This must be set before anything else
# creates an event loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Import application modules
from app.config import settings, is_development
from app.database import engine, AsyncSessionLocal, Base, get_db
from app.services.polling_service import PollingService
from app.services.websocket_manager import websocket_manager
from app.services.diagnostic_engine import DiagnosticEngine
from app.services.snmp_service import SNMPService
from app.services.notification_service import NotificationService
from app.services.alert_escalation import AlertEscalationService

# Import API routers
from app.api import routes
from app.api.websocket import router as websocket_router

# ============================================================================
# Logging Configuration
# ============================================================================

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# Global Services
# ============================================================================

diagnostic_engine = DiagnosticEngine()

snmp_service = SNMPService(
    community=settings.SNMP_COMMUNITY,
    timeout=settings.SNMP_TIMEOUT,
)

polling_service = PollingService(
    db_session_factory=AsyncSessionLocal,
    websocket_manager=websocket_manager,
    diagnostic_engine=diagnostic_engine,
    snmp_service=snmp_service,
    poll_interval=settings.POLL_INTERVAL_SECONDS,
    debounce_window=settings.DEBOUNCE_WAIT_SECONDS
)

notification_service = NotificationService()

alert_escalation_service = AlertEscalationService(
    db_session_factory=AsyncSessionLocal
)

# ============================================================================
# Lifespan Manager
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    
    # ===== STARTUP =====
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.APP_NAME} Starting Up...")
    logger.info(f"📊 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔄 Poll Interval: {settings.POLL_INTERVAL_SECONDS}s")
    logger.info(f"⏱️  Debounce Window: {settings.DEBOUNCE_WAIT_SECONDS}s")
    logger.info("=" * 60)
    
    try:
        # Create database tables
        logger.info("📁 Creating database tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created/verified")
        
        # Start polling service
        logger.info("🔄 Starting polling service...")
        await polling_service.start_polling()
        logger.info("✅ Polling service started")
        
        # Start escalation service
        logger.info("📈 Starting escalation service...")
        await alert_escalation_service.start()
        logger.info("✅ Escalation service started")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise
    
    yield
    
    # ===== SHUTDOWN =====
    logger.info("=" * 60)
    logger.info("🛑 OIC NetRadar Shutting Down...")
    
    try:
        await polling_service.stop_polling()
        await alert_escalation_service.stop()
        await engine.dispose()
        logger.info("✅ Shutdown complete")
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")
    
    logger.info("=" * 60)

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="""
    Enterprise-grade network and server monitoring system for Oromia Insurance Company.
    
    Features:
    - Real-time device monitoring across 62 branches
    - Root cause diagnostic engine
    - Automatic alert escalation
    - WebSocket real-time updates
    - Historical reporting
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# ============================================================================
# CORS Configuration
# ============================================================================

# Get CORS origins from settings
cors_origins = settings.CORS_ORIGINS

if is_development():
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Include Routers
# ============================================================================

app.include_router(routes.router)
app.include_router(websocket_router)

# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "environment": settings.ENVIRONMENT
    }

@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Enterprise Network Monitoring System",
        "documentation": "/api/docs",
        "health": "/health",
        "websocket": "ws://localhost:8000/ws",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if is_development() else "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

# ============================================================================
# Development Server Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )