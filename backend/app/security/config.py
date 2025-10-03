"""
Security configuration and settings
"""

import os
from datetime import timedelta
from typing import Dict, List, Optional

class SecurityConfig:
    """Centralized security configuration"""
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-jwt-secret-key-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "1"))
    JWT_REFRESH_EXPIRATION_DAYS = int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "7"))
    JWT_CLOCK_SKEW_SECONDS = int(os.getenv("JWT_CLOCK_SKEW_SECONDS", "30"))
    JWT_ROTATION_THRESHOLD_MINUTES = int(os.getenv("JWT_ROTATION_THRESHOLD_MINUTES", "15"))
    JWT_ISSUER = os.getenv("JWT_ISSUER", "comicguess-api")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "comicguess-app")
    
    # CSRF Protection
    CSRF_SECRET_KEY = os.getenv("CSRF_SECRET_KEY", "your-csrf-secret-key-change-in-production")
    CSRF_TOKEN_LIFETIME_HOURS = int(os.getenv("CSRF_TOKEN_LIFETIME_HOURS", "1"))
    CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "true").lower() == "true"
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = "strict"
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
    RATE_LIMIT_GUESS_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_GUESS_REQUESTS_PER_MINUTE", "10"))
    RATE_LIMIT_BURST_SIZE = int(os.getenv("RATE_LIMIT_BURST_SIZE", "10"))
    
    # Content Moderation
    CONTENT_MODERATION_ENABLED = os.getenv("CONTENT_MODERATION_ENABLED", "true").lower() == "true"
    PROFANITY_FILTER_STRICT_MODE = os.getenv("PROFANITY_FILTER_STRICT_MODE", "false").lower() == "true"
    AUTO_MODERATE_USERNAMES = os.getenv("AUTO_MODERATE_USERNAMES", "true").lower() == "true"
    AUTO_MODERATE_GUESSES = os.getenv("AUTO_MODERATE_GUESSES", "true").lower() == "true"
    
    # CAPTCHA Configuration
    RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
    RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
    CAPTCHA_ENABLED = bool(RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY)
    CAPTCHA_THRESHOLD_SCORE = float(os.getenv("CAPTCHA_THRESHOLD_SCORE", "0.5"))
    
    # Threat Protection
    THREAT_PROTECTION_ENABLED = os.getenv("THREAT_PROTECTION_ENABLED", "true").lower() == "true"
    THREAT_DETECTION_SENSITIVITY = os.getenv("THREAT_DETECTION_SENSITIVITY", "medium")  # low, medium, high
    PROGRESSIVE_PENALTIES_ENABLED = os.getenv("PROGRESSIVE_PENALTIES_ENABLED", "true").lower() == "true"
    
    # Data Protection
    DATA_ENCRYPTION_KEY = os.getenv("DATA_ENCRYPTION_KEY")
    PII_ENCRYPTION_ENABLED = os.getenv("PII_ENCRYPTION_ENABLED", "true").lower() == "true"
    DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "365"))
    AUTO_PURGE_EXPIRED_DATA = os.getenv("AUTO_PURGE_EXPIRED_DATA", "false").lower() == "true"
    
    # Secrets Management
    AZURE_KEYVAULT_URL = os.getenv("AZURE_KEYVAULT_URL")
    SECRETS_ROTATION_ENABLED = os.getenv("SECRETS_ROTATION_ENABLED", "true").lower() == "true"
    SECRETS_ROTATION_INTERVAL_DAYS = int(os.getenv("SECRETS_ROTATION_INTERVAL_DAYS", "90"))
    
    # Security Headers
    HSTS_MAX_AGE = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 year
    CSP_REPORT_URI = os.getenv("CSP_REPORT_URI")
    SECURITY_HEADERS_ENABLED = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
    
    # CORS Configuration
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    CORS_MAX_AGE = int(os.getenv("CORS_MAX_AGE", "600"))
    
    # Session Security
    SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    SESSION_ABSOLUTE_TIMEOUT_HOURS = int(os.getenv("SESSION_ABSOLUTE_TIMEOUT_HOURS", "24"))
    MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "5"))
    SESSION_IP_VALIDATION = os.getenv("SESSION_IP_VALIDATION", "true").lower() == "true"
    
    # Account Security
    MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    ACCOUNT_LOCKOUT_DURATION_MINUTES = int(os.getenv("ACCOUNT_LOCKOUT_DURATION_MINUTES", "15"))
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
    PASSWORD_REQUIRE_COMPLEXITY = os.getenv("PASSWORD_REQUIRE_COMPLEXITY", "true").lower() == "true"
    
    # Audit and Compliance
    AUDIT_LOGGING_ENABLED = os.getenv("AUDIT_LOGGING_ENABLED", "true").lower() == "true"
    GDPR_COMPLIANCE_MODE = os.getenv("GDPR_COMPLIANCE_MODE", "true").lower() == "true"
    DATA_EXPORT_ENABLED = os.getenv("DATA_EXPORT_ENABLED", "true").lower() == "true"
    RIGHT_TO_DELETION_ENABLED = os.getenv("RIGHT_TO_DELETION_ENABLED", "true").lower() == "true"
    
    # Monitoring and Alerting
    SECURITY_MONITORING_ENABLED = os.getenv("SECURITY_MONITORING_ENABLED", "true").lower() == "true"
    ALERT_ON_SECURITY_EVENTS = os.getenv("ALERT_ON_SECURITY_EVENTS", "true").lower() == "true"
    SECURITY_METRICS_RETENTION_DAYS = int(os.getenv("SECURITY_METRICS_RETENTION_DAYS", "90"))
    
    @classmethod
    def get_jwt_config(cls) -> Dict:
        """Get JWT configuration"""
        return {
            "secret_key": cls.JWT_SECRET_KEY,
            "algorithm": cls.JWT_ALGORITHM,
            "expiration_hours": cls.JWT_EXPIRATION_HOURS,
            "refresh_expiration_days": cls.JWT_REFRESH_EXPIRATION_DAYS,
            "clock_skew_seconds": cls.JWT_CLOCK_SKEW_SECONDS,
            "rotation_threshold_minutes": cls.JWT_ROTATION_THRESHOLD_MINUTES,
            "issuer": cls.JWT_ISSUER,
            "audience": cls.JWT_AUDIENCE
        }
    
    @classmethod
    def get_csrf_config(cls) -> Dict:
        """Get CSRF configuration"""
        return {
            "secret_key": cls.CSRF_SECRET_KEY,
            "token_lifetime": timedelta(hours=cls.CSRF_TOKEN_LIFETIME_HOURS),
            "cookie_secure": cls.CSRF_COOKIE_SECURE,
            "cookie_httponly": cls.CSRF_COOKIE_HTTPONLY,
            "cookie_samesite": cls.CSRF_COOKIE_SAMESITE
        }
    
    @classmethod
    def get_rate_limit_config(cls) -> Dict:
        """Get rate limiting configuration"""
        return {
            "requests_per_minute": cls.RATE_LIMIT_REQUESTS_PER_MINUTE,
            "guess_requests_per_minute": cls.RATE_LIMIT_GUESS_REQUESTS_PER_MINUTE,
            "burst_size": cls.RATE_LIMIT_BURST_SIZE
        }
    
    @classmethod
    def get_content_moderation_config(cls) -> Dict:
        """Get content moderation configuration"""
        return {
            "enabled": cls.CONTENT_MODERATION_ENABLED,
            "strict_mode": cls.PROFANITY_FILTER_STRICT_MODE,
            "auto_moderate_usernames": cls.AUTO_MODERATE_USERNAMES,
            "auto_moderate_guesses": cls.AUTO_MODERATE_GUESSES
        }
    
    @classmethod
    def get_security_headers_config(cls) -> Dict:
        """Get security headers configuration"""
        return {
            "enabled": cls.SECURITY_HEADERS_ENABLED,
            "hsts_max_age": cls.HSTS_MAX_AGE,
            "csp_report_uri": cls.CSP_REPORT_URI
        }
    
    @classmethod
    def get_session_config(cls) -> Dict:
        """Get session security configuration"""
        return {
            "timeout_minutes": cls.SESSION_TIMEOUT_MINUTES,
            "absolute_timeout_hours": cls.SESSION_ABSOLUTE_TIMEOUT_HOURS,
            "max_concurrent_sessions": cls.MAX_CONCURRENT_SESSIONS,
            "ip_validation": cls.SESSION_IP_VALIDATION
        }
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment"""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate security configuration and return warnings"""
        warnings = []
        
        # Check for default/weak secrets in production
        if cls.is_production():
            if "change-in-production" in cls.JWT_SECRET_KEY:
                warnings.append("JWT secret key is using default value in production")
            
            if "change-in-production" in cls.CSRF_SECRET_KEY:
                warnings.append("CSRF secret key is using default value in production")
            
            if not cls.AZURE_KEYVAULT_URL:
                warnings.append("Azure Key Vault URL not configured in production")
            
            if not cls.CAPTCHA_ENABLED:
                warnings.append("CAPTCHA not configured in production")
        
        # Check for security feature enablement
        if not cls.CONTENT_MODERATION_ENABLED:
            warnings.append("Content moderation is disabled")
        
        if not cls.THREAT_PROTECTION_ENABLED:
            warnings.append("Threat protection is disabled")
        
        if not cls.SECURITY_HEADERS_ENABLED:
            warnings.append("Security headers are disabled")
        
        # Check for weak settings
        if cls.JWT_EXPIRATION_HOURS > 24:
            warnings.append("JWT expiration time is longer than 24 hours")
        
        if cls.PASSWORD_MIN_LENGTH < 8:
            warnings.append("Password minimum length is less than 8 characters")
        
        if cls.MAX_LOGIN_ATTEMPTS > 10:
            warnings.append("Maximum login attempts is set too high")
        
        return warnings

# Global security configuration instance
security_config = SecurityConfig()

# Validate configuration on import
config_warnings = security_config.validate_config()
if config_warnings:
    import logging
    logger = logging.getLogger(__name__)
    for warning in config_warnings:
        logger.warning(f"Security configuration warning: {warning}")