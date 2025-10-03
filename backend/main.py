from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from app.api.users import router as users_router
from app.api.game import router as game_router
from app.api.images import router as images_router
from app.api.image_versions import router as image_versions_router
from app.api.monitoring import router as monitoring_router
from app.api.cache import router as cache_router
from app.api.health import router as health_router, startup_health_checks
from app.middleware.rate_limiting import rate_limit_middleware
from app.security.threat_protection import ThreatProtectionMiddleware, CaptchaProvider
from app.auth.middleware import add_security_headers
from app.security.content_moderation import security_headers
from app.security.csrf_protection import CSRFMiddleware, csrf_protection

# Load environment variables
load_dotenv()

app = FastAPI(
    title="ComicGuess API",
    description="Daily comic character guessing game API",
    version="1.0.0"
)

# Initialize threat protection with CAPTCHA
captcha_provider = None
captcha_secret = os.getenv("RECAPTCHA_SECRET_KEY")
captcha_site_key = os.getenv("RECAPTCHA_SITE_KEY")

if captcha_secret and captcha_site_key:
    captcha_provider = CaptchaProvider(captcha_secret, captcha_site_key)

threat_protection = ThreatProtectionMiddleware(captcha_provider)

# Initialize CSRF protection
csrf_middleware = CSRFMiddleware(
    csrf_protection,
    protected_methods={"POST", "PUT", "PATCH", "DELETE"},
    exempt_paths={"/health", "/", "/api/auth/login", "/api/auth/register"}
)

# Add security middlewares (order matters)
app.middleware("http")(add_security_headers)
app.middleware("http")(csrf_middleware)
app.middleware("http")(threat_protection)
app.middleware("http")(rate_limit_middleware)

# Configure CORS with security considerations
allowed_origins = [
    "http://localhost:3000",  # Local development
    "https://localhost:3000",  # Local HTTPS development
]

# Add production origins from environment
production_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if production_origins and production_origins[0]:  # Check if not empty
    allowed_origins.extend([origin.strip() for origin in production_origins])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods only
    allow_headers=[
        "Authorization",
        "Content-Type", 
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token"
    ],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Include API routers
app.include_router(users_router)
app.include_router(game_router)
app.include_router(images_router)
app.include_router(image_versions_router)
app.include_router(cache_router)
app.include_router(monitoring_router, prefix="/api/monitor", tags=["monitoring"])
app.include_router(health_router, prefix="/api", tags=["health"])

@app.get("/")
async def root():
    return {"message": "ComicGuess API is running"}

@app.get("/health")
async def basic_health_check():
    """Basic health check for load balancers"""
    return {"status": "healthy", "service": "comicguess-api"}


@app.on_event("startup")
async def startup_event():
    """Application startup event handler"""
    await startup_health_checks()


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler"""
    from app.monitoring.health import health_monitor
    await health_monitor.graceful_shutdown()

@app.get("/api/security/csrf-token")
async def get_csrf_token(user_id: str = None, session_id: str = None):
    """Get a CSRF token for form submissions"""
    from app.security.csrf_protection import generate_csrf_token
    token = generate_csrf_token(user_id, session_id)
    return {"csrf_token": token}

@app.get("/api/security/headers")
async def get_security_info():
    """Get security headers information"""
    headers = security_headers.get_security_headers()
    return {"security_headers": list(headers.keys())}

@app.get("/user/health")
async def user_service_health():
    """Health check endpoint for user service"""
    return {"status": "healthy", "service": "user_management"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)