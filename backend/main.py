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
from app.api.auth import router as auth_router
from app.api.streaks import router as streaks_router
from app.middleware.rate_limiting import rate_limit_middleware
from app.security.threat_protection import ThreatProtectionMiddleware, CaptchaProvider
from app.auth.middleware import add_security_headers
from app.security.content_moderation import security_headers
from app.security.csrf_protection import CSRFMiddleware, csrf_protection

# Load environment variables
load_dotenv()

app = FastAPI(
    title="ComicGuess API",
    description="""
    Daily comic character guessing game API.
    
    ## Features
    
    * **Daily Puzzles**: Get new character puzzles for Marvel, DC, and Image Comics
    * **Guess Validation**: Submit and validate character name guesses
    * **User Management**: Track user statistics and streaks
    * **Image Serving**: Retrieve character images with CDN optimization
    * **Rate Limiting**: Built-in protection against abuse
    
    ## Authentication
    
    Most endpoints require JWT authentication. Include the token in the Authorization header:
    ```
    Authorization: Bearer <your-jwt-token>
    ```
    
    ## Rate Limits
    
    - Guess submissions: 30 per minute
    - General API requests: 200 per minute
    
    ## Environments
    
    - **Production**: https://api.comicguess.com
    - **Staging**: https://comicguess-backend-staging.azurewebsites.net
    - **Development**: http://localhost:8000
    """,
    version="1.0.0",
    contact={
        "name": "ComicGuess Support",
        "url": "https://comicguess.com/support",
        "email": "support@comicguess.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {
            "url": "https://api.comicguess.com",
            "description": "Production server"
        },
        {
            "url": "https://comicguess-backend-staging.azurewebsites.net",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ],
    openapi_tags=[
        {
            "name": "game",
            "description": "Game operations - puzzle retrieval and guess submission"
        },
        {
            "name": "users",
            "description": "User management and statistics"
        },
        {
            "name": "images",
            "description": "Character image serving and management"
        },
        {
            "name": "health",
            "description": "Health check and monitoring endpoints"
        },
        {
            "name": "security",
            "description": "Security and authentication endpoints"
        },
        {
            "name": "authentication",
            "description": "User authentication and authorization"
        },
        {
            "name": "streaks",
            "description": "User streak management"
        }
    ]
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
    "http://127.0.0.1:3000",  # Local development (127.0.0.1)
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
app.include_router(auth_router, prefix="/api")
app.include_router(streaks_router, prefix="/api")
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
    
    # Quick Cosmos DB health check
    try:
        from app.database import get_cosmos_db
        cosmos_db = await get_cosmos_db()
        health_result = await cosmos_db.health_check()
        if health_result.get("status") == "healthy":
            print(f"✅ Cosmos DB connected: {health_result.get('database')}")
        else:
            print(f"⚠️  Cosmos DB issue: {health_result.get('error', 'Unknown')}")
    except Exception as e:
        print(f"❌ Cosmos DB connection failed: {e}")


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