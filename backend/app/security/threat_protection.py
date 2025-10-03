"""
Comprehensive threat protection system implementing OWASP ASVS guidelines
"""

import time
import hashlib
import logging
import asyncio
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import re

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import httpx

logger = logging.getLogger(__name__)

class ThreatLevel(Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ThreatEvent:
    """Represents a detected threat event"""
    timestamp: datetime
    ip_address: str
    user_id: Optional[str]
    threat_type: str
    threat_level: ThreatLevel
    details: Dict
    blocked: bool = False

@dataclass
class ProgressivePenalty:
    """Progressive penalty configuration"""
    violation_count: int = 0
    penalty_duration: int = 60  # seconds
    last_violation: Optional[datetime] = None
    
    def calculate_penalty(self) -> int:
        """Calculate penalty duration based on violation count"""
        if self.violation_count == 0:
            return 0
        
        # Progressive penalties: 1min, 5min, 15min, 1hr, 24hr
        penalties = [60, 300, 900, 3600, 86400]
        penalty_index = min(self.violation_count - 1, len(penalties) - 1)
        return penalties[penalty_index]
    
    def add_violation(self):
        """Record a new violation"""
        self.violation_count += 1
        self.last_violation = datetime.utcnow()
        self.penalty_duration = self.calculate_penalty()

class CaptchaProvider:
    """CAPTCHA integration for abuse prevention"""
    
    def __init__(self, secret_key: str, site_key: str):
        self.secret_key = secret_key
        self.site_key = site_key
        self.verify_url = "https://www.google.com/recaptcha/api/siteverify"
    
    async def verify_captcha(self, captcha_response: str, user_ip: str) -> bool:
        """
        Verify CAPTCHA response with Google reCAPTCHA
        
        Args:
            captcha_response: The response token from the client
            user_ip: Client IP address
            
        Returns:
            True if CAPTCHA is valid, False otherwise
        """
        if not captcha_response:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.verify_url,
                    data={
                        'secret': self.secret_key,
                        'response': captcha_response,
                        'remoteip': user_ip
                    },
                    timeout=10.0
                )
                
                result = response.json()
                
                if result.get('success'):
                    # Check score for reCAPTCHA v3 (optional)
                    score = result.get('score', 1.0)
                    return score >= 0.5  # Adjust threshold as needed
                
                logger.warning(f"CAPTCHA verification failed: {result.get('error-codes', [])}")
                return False
                
        except Exception as e:
            logger.error(f"CAPTCHA verification error: {e}")
            return False

class ThreatDetector:
    """Advanced threat detection system"""
    
    def __init__(self):
        self.threat_events: List[ThreatEvent] = []
        self.ip_penalties: Dict[str, ProgressivePenalty] = defaultdict(ProgressivePenalty)
        self.user_penalties: Dict[str, ProgressivePenalty] = defaultdict(ProgressivePenalty)
        self.suspicious_patterns = self._load_suspicious_patterns()
        self.blocked_ips: Set[str] = set()
        self.blocked_users: Set[str] = set()
        
        # Abuse detection thresholds
        self.thresholds = {
            'rapid_requests': {'count': 20, 'window': 60},  # 20 requests in 1 minute
            'failed_guesses': {'count': 10, 'window': 300},  # 10 failed guesses in 5 minutes
            'pattern_matching': {'count': 5, 'window': 600},  # 5 pattern matches in 10 minutes
            'captcha_failures': {'count': 3, 'window': 300},  # 3 CAPTCHA failures in 5 minutes
        }
    
    def _load_suspicious_patterns(self) -> List[re.Pattern]:
        """Load patterns that indicate suspicious behavior"""
        patterns = [
            # Bot-like behavior patterns
            re.compile(r'^(bot|crawler|spider|scraper)', re.IGNORECASE),
            re.compile(r'(automated|script|tool)', re.IGNORECASE),
            
            # Injection attempt patterns
            re.compile(r'[<>"\'].*?[<>"\']', re.IGNORECASE),
            re.compile(r'(union|select|insert|update|delete|drop)', re.IGNORECASE),
            re.compile(r'(javascript|vbscript|onload|onerror)', re.IGNORECASE),
            
            # Enumeration patterns
            re.compile(r'^(admin|test|user|guest|root)', re.IGNORECASE),
            re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'),  # IP addresses as usernames
            
            # Brute force patterns
            re.compile(r'^.{1,2}$|^.{50,}$'),  # Very short or very long inputs
        ]
        return patterns
    
    def detect_threats(self, request: Request, user_id: Optional[str] = None, 
                      guess: Optional[str] = None) -> List[ThreatEvent]:
        """
        Detect potential threats in the request
        
        Args:
            request: FastAPI request object
            user_id: User ID if authenticated
            guess: Character guess if applicable
            
        Returns:
            List of detected threat events
        """
        threats = []
        ip_address = self._get_client_ip(request)
        current_time = datetime.utcnow()
        
        # Check if IP or user is already blocked
        if ip_address in self.blocked_ips:
            threats.append(ThreatEvent(
                timestamp=current_time,
                ip_address=ip_address,
                user_id=user_id,
                threat_type="blocked_ip",
                threat_level=ThreatLevel.HIGH,
                details={"reason": "IP address is blocked"},
                blocked=True
            ))
        
        if user_id and user_id in self.blocked_users:
            threats.append(ThreatEvent(
                timestamp=current_time,
                ip_address=ip_address,
                user_id=user_id,
                threat_type="blocked_user",
                threat_level=ThreatLevel.HIGH,
                details={"reason": "User account is blocked"},
                blocked=True
            ))
        
        # Detect rapid requests
        rapid_threat = self._detect_rapid_requests(ip_address, user_id, current_time)
        if rapid_threat:
            threats.append(rapid_threat)
        
        # Detect suspicious patterns in guess
        if guess:
            pattern_threat = self._detect_suspicious_patterns(
                ip_address, user_id, guess, current_time
            )
            if pattern_threat:
                threats.append(pattern_threat)
        
        # Detect user agent anomalies
        ua_threat = self._detect_user_agent_anomalies(request, ip_address, user_id, current_time)
        if ua_threat:
            threats.append(ua_threat)
        
        # Store threat events
        self.threat_events.extend(threats)
        
        # Clean old events (keep last 24 hours)
        cutoff_time = current_time - timedelta(hours=24)
        self.threat_events = [
            event for event in self.threat_events 
            if event.timestamp > cutoff_time
        ]
        
        return threats
    
    def _detect_rapid_requests(self, ip_address: str, user_id: Optional[str], 
                              current_time: datetime) -> Optional[ThreatEvent]:
        """Detect rapid request patterns"""
        window_start = current_time - timedelta(seconds=self.thresholds['rapid_requests']['window'])
        
        # Count recent requests from this IP
        ip_requests = [
            event for event in self.threat_events
            if event.ip_address == ip_address and event.timestamp > window_start
        ]
        
        if len(ip_requests) >= self.thresholds['rapid_requests']['count']:
            return ThreatEvent(
                timestamp=current_time,
                ip_address=ip_address,
                user_id=user_id,
                threat_type="rapid_requests",
                threat_level=ThreatLevel.MEDIUM,
                details={
                    "request_count": len(ip_requests),
                    "window_seconds": self.thresholds['rapid_requests']['window']
                }
            )
        
        return None
    
    def _detect_suspicious_patterns(self, ip_address: str, user_id: Optional[str], 
                                   guess: str, current_time: datetime) -> Optional[ThreatEvent]:
        """Detect suspicious patterns in user input"""
        for pattern in self.suspicious_patterns:
            if pattern.search(guess):
                return ThreatEvent(
                    timestamp=current_time,
                    ip_address=ip_address,
                    user_id=user_id,
                    threat_type="suspicious_pattern",
                    threat_level=ThreatLevel.MEDIUM,
                    details={
                        "pattern": pattern.pattern,
                        "input": guess[:100]  # Truncate for logging
                    }
                )
        
        return None
    
    def _detect_user_agent_anomalies(self, request: Request, ip_address: str, 
                                    user_id: Optional[str], current_time: datetime) -> Optional[ThreatEvent]:
        """Detect suspicious user agent patterns"""
        user_agent = request.headers.get("User-Agent", "").lower()
        
        # Check for missing or suspicious user agents
        if not user_agent or len(user_agent) < 10:
            return ThreatEvent(
                timestamp=current_time,
                ip_address=ip_address,
                user_id=user_id,
                threat_type="suspicious_user_agent",
                threat_level=ThreatLevel.LOW,
                details={"user_agent": user_agent}
            )
        
        # Check for bot indicators
        bot_indicators = ['bot', 'crawler', 'spider', 'scraper', 'automated']
        if any(indicator in user_agent for indicator in bot_indicators):
            return ThreatEvent(
                timestamp=current_time,
                ip_address=ip_address,
                user_id=user_id,
                threat_type="bot_user_agent",
                threat_level=ThreatLevel.MEDIUM,
                details={"user_agent": user_agent}
            )
        
        return None
    
    def apply_progressive_penalties(self, threats: List[ThreatEvent]) -> Dict[str, int]:
        """
        Apply progressive penalties based on threat events
        
        Returns:
            Dictionary with penalty durations for IPs and users
        """
        penalties = {}
        
        for threat in threats:
            if threat.threat_level in [ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                # Apply IP penalty
                ip_penalty = self.ip_penalties[threat.ip_address]
                ip_penalty.add_violation()
                penalties[f"ip:{threat.ip_address}"] = ip_penalty.penalty_duration
                
                # Apply user penalty if user is identified
                if threat.user_id:
                    user_penalty = self.user_penalties[threat.user_id]
                    user_penalty.add_violation()
                    penalties[f"user:{threat.user_id}"] = user_penalty.penalty_duration
                
                # Block for critical threats
                if threat.threat_level == ThreatLevel.CRITICAL:
                    self.blocked_ips.add(threat.ip_address)
                    if threat.user_id:
                        self.blocked_users.add(threat.user_id)
        
        return penalties
    
    def is_blocked(self, ip_address: str, user_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if IP or user is currently blocked
        
        Returns:
            (is_blocked, reason)
        """
        current_time = datetime.utcnow()
        
        # Check IP penalty
        if ip_address in self.ip_penalties:
            penalty = self.ip_penalties[ip_address]
            if penalty.last_violation:
                time_since_violation = (current_time - penalty.last_violation).total_seconds()
                if time_since_violation < penalty.penalty_duration:
                    remaining = penalty.penalty_duration - time_since_violation
                    return True, f"IP blocked for {int(remaining)} more seconds"
        
        # Check user penalty
        if user_id and user_id in self.user_penalties:
            penalty = self.user_penalties[user_id]
            if penalty.last_violation:
                time_since_violation = (current_time - penalty.last_violation).total_seconds()
                if time_since_violation < penalty.penalty_duration:
                    remaining = penalty.penalty_duration - time_since_violation
                    return True, f"User blocked for {int(remaining)} more seconds"
        
        # Check permanent blocks
        if ip_address in self.blocked_ips:
            return True, "IP address permanently blocked"
        
        if user_id and user_id in self.blocked_users:
            return True, "User account permanently blocked"
        
        return False, None
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def get_threat_summary(self, hours: int = 24) -> Dict:
        """Get threat detection summary for monitoring"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_threats = [
            event for event in self.threat_events
            if event.timestamp > cutoff_time
        ]
        
        summary = {
            "total_threats": len(recent_threats),
            "threats_by_type": defaultdict(int),
            "threats_by_level": defaultdict(int),
            "blocked_ips": len(self.blocked_ips),
            "blocked_users": len(self.blocked_users),
            "active_penalties": {
                "ip_penalties": len([p for p in self.ip_penalties.values() if p.violation_count > 0]),
                "user_penalties": len([p for p in self.user_penalties.values() if p.violation_count > 0])
            }
        }
        
        for threat in recent_threats:
            summary["threats_by_type"][threat.threat_type] += 1
            summary["threats_by_level"][threat.threat_level.value] += 1
        
        return summary

class ThreatProtectionMiddleware:
    """FastAPI middleware for threat protection"""
    
    def __init__(self, captcha_provider: Optional[CaptchaProvider] = None):
        self.detector = ThreatDetector()
        self.captcha_provider = captcha_provider
        self.captcha_required_endpoints = {'/guess'}  # Endpoints that may require CAPTCHA
    
    async def __call__(self, request: Request, call_next):
        """Process request through threat protection"""
        try:
            # Extract user information
            user_id = self._extract_user_id(request)
            ip_address = self.detector._get_client_ip(request)
            
            # Check if already blocked
            is_blocked, block_reason = self.detector.is_blocked(ip_address, user_id)
            if is_blocked:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Access Blocked",
                        "detail": block_reason,
                        "blocked": True
                    }
                )
            
            # For guess endpoints, check if CAPTCHA is required
            if (request.url.path in self.captcha_required_endpoints and 
                self.captcha_provider and request.method == "POST"):
                
                captcha_required = await self._should_require_captcha(ip_address, user_id)
                if captcha_required:
                    # Check for CAPTCHA in request
                    body = await request.body()
                    if body:
                        try:
                            data = json.loads(body)
                            captcha_response = data.get('captcha_response')
                            
                            if not captcha_response:
                                return JSONResponse(
                                    status_code=400,
                                    content={
                                        "error": "CAPTCHA Required",
                                        "detail": "Please complete the CAPTCHA verification",
                                        "captcha_required": True,
                                        "site_key": self.captcha_provider.site_key
                                    }
                                )
                            
                            # Verify CAPTCHA
                            captcha_valid = await self.captcha_provider.verify_captcha(
                                captcha_response, ip_address
                            )
                            
                            if not captcha_valid:
                                # Record CAPTCHA failure as threat
                                threat = ThreatEvent(
                                    timestamp=datetime.utcnow(),
                                    ip_address=ip_address,
                                    user_id=user_id,
                                    threat_type="captcha_failure",
                                    threat_level=ThreatLevel.MEDIUM,
                                    details={"captcha_response": captcha_response[:20]}
                                )
                                self.detector.threat_events.append(threat)
                                
                                return JSONResponse(
                                    status_code=400,
                                    content={
                                        "error": "CAPTCHA Verification Failed",
                                        "detail": "Please try the CAPTCHA again",
                                        "captcha_required": True,
                                        "site_key": self.captcha_provider.site_key
                                    }
                                )
                        except json.JSONDecodeError:
                            pass
            
            # Process request normally
            response = await call_next(request)
            
            # Detect threats after processing (for failed guesses, etc.)
            if hasattr(request.state, 'guess_failed') and request.state.guess_failed:
                threat = ThreatEvent(
                    timestamp=datetime.utcnow(),
                    ip_address=ip_address,
                    user_id=user_id,
                    threat_type="failed_guess",
                    threat_level=ThreatLevel.LOW,
                    details={"endpoint": request.url.path}
                )
                self.detector.threat_events.append(threat)
            
            return response
            
        except Exception as e:
            logger.error(f"Threat protection middleware error: {e}")
            # Continue processing on middleware errors
            return await call_next(request)
    
    def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from app.auth.jwt_handler import verify_token
                token = auth_header.split(" ")[1]
                payload = verify_token(token)
                return payload.get("sub")
            except Exception:
                pass
        return None
    
    async def _should_require_captcha(self, ip_address: str, user_id: Optional[str]) -> bool:
        """Determine if CAPTCHA should be required based on threat history"""
        current_time = datetime.utcnow()
        window_start = current_time - timedelta(minutes=30)
        
        # Check recent threat events
        recent_threats = [
            event for event in self.detector.threat_events
            if (event.ip_address == ip_address or event.user_id == user_id) and
               event.timestamp > window_start and
               event.threat_level in [ThreatLevel.MEDIUM, ThreatLevel.HIGH]
        ]
        
        # Require CAPTCHA if there are 2+ medium/high threats in last 30 minutes
        return len(recent_threats) >= 2

# Global threat protection instance
threat_protection = ThreatProtectionMiddleware()