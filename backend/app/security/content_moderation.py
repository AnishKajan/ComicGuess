"""
Content moderation and profanity filtering utilities
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ModerationAction(Enum):
    """Actions that can be taken on moderated content"""
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REVIEW = "review"

class ContentCategory(Enum):
    """Categories of content for moderation"""
    USERNAME = "username"
    GUESS = "guess"
    COMMENT = "comment"
    PROFILE = "profile"

@dataclass
class ModerationResult:
    """Result of content moderation"""
    action: ModerationAction
    confidence: float
    reasons: List[str]
    filtered_content: Optional[str] = None
    metadata: Dict = None

class ProfanityFilter:
    """Advanced profanity filtering with context awareness"""
    
    def __init__(self):
        # Basic profanity list (sanitized for code)
        self.profanity_words = {
            # Mild profanity
            "damn", "hell", "crap", "suck", "stupid", "idiot", "moron",
            # Placeholder for actual profanity words - in production, load from secure config
            "badword1", "badword2", "offensive1", "offensive2"
        }
        
        # Leetspeak and obfuscation patterns
        self.leetspeak_map = {
            '4': 'a', '@': 'a', '3': 'e', '1': 'i', '!': 'i',
            '0': 'o', '5': 's', '$': 's', '7': 't', '+': 't'
        }
        
        # Context-aware patterns
        self.context_patterns = {
            'repeated_chars': re.compile(r'(.)\1{2,}'),  # aaaaaa
            'excessive_caps': re.compile(r'[A-Z]{4,}'),   # AAAA
            'mixed_case_spam': re.compile(r'([a-z][A-Z]){3,}'),  # aBcDeFg
            'number_substitution': re.compile(r'[0-9@$!+]{2,}'),  # 1337 speak
        }
        
        # Severity levels
        self.severity_levels = {
            'mild': 0.3,
            'moderate': 0.6,
            'severe': 0.9
        }
        
        # Whitelist for gaming terms that might trigger false positives
        self.gaming_whitelist = {
            'kill', 'die', 'dead', 'shoot', 'fight', 'battle', 'war',
            'destroy', 'attack', 'hit', 'strike', 'crush', 'smash'
        }
        
        # Character name exceptions (comic book characters with potentially flagged names)
        self.character_exceptions = {
            'deadpool', 'killmonger', 'deathstroke', 'punisher',
            'destroyer', 'warpath', 'havok', 'psylocke'
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for consistent filtering"""
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower().strip()
        
        # Remove excessive whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Decode leetspeak
        for leet, normal in self.leetspeak_map.items():
            normalized = normalized.replace(leet, normal)
        
        # Remove non-alphanumeric characters for pattern matching
        pattern_text = re.sub(r'[^a-z0-9\s]', '', normalized)
        
        return pattern_text
    
    def check_profanity(self, text: str, category: ContentCategory) -> ModerationResult:
        """Check text for profanity and inappropriate content"""
        if not text:
            return ModerationResult(ModerationAction.ALLOW, 1.0, [])
        
        normalized = self.normalize_text(text)
        reasons = []
        confidence = 0.0
        action = ModerationAction.ALLOW
        
        # Check for direct profanity matches
        profanity_score = self._check_direct_profanity(normalized, reasons)
        confidence = max(confidence, profanity_score)
        
        # Check for obfuscated profanity
        obfuscation_score = self._check_obfuscated_profanity(text, reasons)
        confidence = max(confidence, obfuscation_score)
        
        # Check for spam patterns
        spam_score = self._check_spam_patterns(text, reasons)
        confidence = max(confidence, spam_score)
        
        # Category-specific checks
        category_score = self._check_category_specific(text, category, reasons)
        confidence = max(confidence, category_score)
        
        # Determine action based on confidence
        if confidence >= 0.9:
            action = ModerationAction.BLOCK
        elif confidence >= 0.6:
            action = ModerationAction.REVIEW
        elif confidence >= 0.3:
            action = ModerationAction.WARN
        else:
            action = ModerationAction.ALLOW
        
        # Apply whitelist exceptions
        if self._is_whitelisted(normalized):
            action = ModerationAction.ALLOW
            reasons.append("Whitelisted gaming/character term")
        
        return ModerationResult(
            action=action,
            confidence=confidence,
            reasons=reasons,
            filtered_content=self._filter_content(text, action) if action != ModerationAction.ALLOW else None
        )
    
    def _check_direct_profanity(self, normalized_text: str, reasons: List[str]) -> float:
        """Check for direct profanity matches"""
        max_score = 0.0
        words = normalized_text.split()
        
        for word in words:
            if word in self.profanity_words:
                reasons.append(f"Contains profanity: {word}")
                max_score = max(max_score, 0.8)
        
        return max_score
    
    def _check_obfuscated_profanity(self, text: str, reasons: List[str]) -> float:
        """Check for obfuscated or disguised profanity"""
        max_score = 0.0
        
        # Check for character substitution patterns
        for profane_word in self.profanity_words:
            # Create regex pattern for obfuscated versions
            pattern = self._create_obfuscation_pattern(profane_word)
            if re.search(pattern, text, re.IGNORECASE):
                reasons.append(f"Contains obfuscated profanity: {profane_word}")
                max_score = max(max_score, 0.7)
        
        return max_score
    
    def _create_obfuscation_pattern(self, word: str) -> str:
        """Create regex pattern to match obfuscated versions of a word"""
        pattern = ""
        for char in word:
            if char == 'a':
                pattern += r'[a@4]'
            elif char == 'e':
                pattern += r'[e3]'
            elif char == 'i':
                pattern += r'[i1!]'
            elif char == 'o':
                pattern += r'[o0]'
            elif char == 's':
                pattern += r'[s5$]'
            elif char == 't':
                pattern += r'[t7+]'
            else:
                pattern += char
        
        return pattern
    
    def _check_spam_patterns(self, text: str, reasons: List[str]) -> float:
        """Check for spam-like patterns"""
        max_score = 0.0
        
        # Repeated characters
        if self.context_patterns['repeated_chars'].search(text):
            reasons.append("Contains repeated characters")
            max_score = max(max_score, 0.4)
        
        # Excessive caps
        caps_matches = self.context_patterns['excessive_caps'].findall(text)
        if caps_matches and len(''.join(caps_matches)) > len(text) * 0.5:
            reasons.append("Excessive use of capital letters")
            max_score = max(max_score, 0.5)
        
        # Mixed case spam
        if self.context_patterns['mixed_case_spam'].search(text):
            reasons.append("Suspicious mixed case pattern")
            max_score = max(max_score, 0.6)
        
        return max_score
    
    def _check_category_specific(self, text: str, category: ContentCategory, reasons: List[str]) -> float:
        """Apply category-specific moderation rules"""
        max_score = 0.0
        
        if category == ContentCategory.USERNAME:
            # Usernames should be more strictly moderated
            if len(text) < 3:
                reasons.append("Username too short")
                max_score = max(max_score, 0.7)
            
            if re.search(r'^(admin|mod|test|guest|user)\d*$', text, re.IGNORECASE):
                reasons.append("Reserved username pattern")
                max_score = max(max_score, 0.8)
            
            # Check for impersonation attempts
            if re.search(r'(official|staff|support|help)', text, re.IGNORECASE):
                reasons.append("Potential impersonation attempt")
                max_score = max(max_score, 0.9)
        
        elif category == ContentCategory.GUESS:
            # Character guesses should allow comic book character names
            # but block obvious non-character attempts
            if len(text) > 50:
                reasons.append("Guess too long")
                max_score = max(max_score, 0.6)
            
            # Check for obvious spam in guesses
            if re.search(r'(http|www|\.com|\.org)', text, re.IGNORECASE):
                reasons.append("Contains URL-like content")
                max_score = max(max_score, 0.8)
        
        return max_score
    
    def _is_whitelisted(self, normalized_text: str) -> bool:
        """Check if text contains whitelisted terms"""
        words = normalized_text.split()
        
        for word in words:
            if word in self.gaming_whitelist or word in self.character_exceptions:
                return True
        
        return False
    
    def _filter_content(self, text: str, action: ModerationAction) -> str:
        """Filter content based on moderation action"""
        if action == ModerationAction.BLOCK:
            return "[CONTENT BLOCKED]"
        elif action == ModerationAction.REVIEW:
            return "[CONTENT UNDER REVIEW]"
        elif action == ModerationAction.WARN:
            # Replace profanity with asterisks
            filtered = text
            for word in self.profanity_words:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                filtered = pattern.sub('*' * len(word), filtered)
            return filtered
        
        return text

class ContentModerationManager:
    """Comprehensive content moderation system"""
    
    def __init__(self):
        self.profanity_filter = ProfanityFilter()
        self.moderation_log: List[Dict] = []
        self.user_violations: Dict[str, List[Dict]] = {}
        
        # Rate limiting for moderation actions
        self.violation_thresholds = {
            'warnings': 3,      # 3 warnings before review
            'blocks': 1,        # 1 block triggers review
            'reviews': 5        # 5 reviews trigger escalation
        }
    
    def moderate_content(self, content: str, category: ContentCategory, 
                        user_id: Optional[str] = None, context: Optional[Dict] = None) -> ModerationResult:
        """Moderate content with comprehensive checks"""
        try:
            # Basic profanity and content filtering
            result = self.profanity_filter.check_profanity(content, category)
            
            # Add additional context-based checks
            if context:
                result = self._apply_context_moderation(result, content, context)
            
            # Log moderation action
            self._log_moderation(content, category, result, user_id, context)
            
            # Track user violations
            if user_id and result.action in [ModerationAction.WARN, ModerationAction.BLOCK, ModerationAction.REVIEW]:
                self._track_user_violation(user_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error during content moderation: {e}")
            # Fail safe - allow content but log error
            return ModerationResult(
                action=ModerationAction.ALLOW,
                confidence=0.0,
                reasons=[f"Moderation error: {str(e)}"]
            )
    
    def _apply_context_moderation(self, base_result: ModerationResult, content: str, 
                                 context: Dict) -> ModerationResult:
        """Apply additional context-based moderation"""
        additional_reasons = []
        confidence_modifier = 0.0
        
        # Check submission frequency
        if context.get('recent_submissions', 0) > 10:
            additional_reasons.append("High submission frequency")
            confidence_modifier += 0.2
        
        # Check for duplicate content
        if context.get('is_duplicate', False):
            additional_reasons.append("Duplicate content detected")
            confidence_modifier += 0.3
        
        # Check user reputation
        user_reputation = context.get('user_reputation', 1.0)
        if user_reputation < 0.5:
            additional_reasons.append("Low user reputation")
            confidence_modifier += 0.2
        
        # Adjust result based on context
        new_confidence = min(1.0, base_result.confidence + confidence_modifier)
        new_reasons = base_result.reasons + additional_reasons
        
        # Recalculate action based on new confidence
        if new_confidence >= 0.9:
            new_action = ModerationAction.BLOCK
        elif new_confidence >= 0.6:
            new_action = ModerationAction.REVIEW
        elif new_confidence >= 0.3:
            new_action = ModerationAction.WARN
        else:
            new_action = ModerationAction.ALLOW
        
        return ModerationResult(
            action=new_action,
            confidence=new_confidence,
            reasons=new_reasons,
            filtered_content=base_result.filtered_content,
            metadata=context
        )
    
    def _log_moderation(self, content: str, category: ContentCategory, 
                       result: ModerationResult, user_id: Optional[str], 
                       context: Optional[Dict]):
        """Log moderation actions for audit and improvement"""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'content_hash': hashlib.sha256(content.encode()).hexdigest()[:16],
            'category': category.value,
            'action': result.action.value,
            'confidence': result.confidence,
            'reasons': result.reasons,
            'user_id': user_id,
            'context': context or {}
        }
        
        self.moderation_log.append(log_entry)
        
        # Keep only recent logs (last 1000 entries)
        if len(self.moderation_log) > 1000:
            self.moderation_log = self.moderation_log[-1000:]
        
        # Log significant actions
        if result.action in [ModerationAction.BLOCK, ModerationAction.REVIEW]:
            logger.warning(f"Content moderation action: {result.action.value} for user {user_id}, reasons: {result.reasons}")
    
    def _track_user_violation(self, user_id: str, result: ModerationResult):
        """Track user violations for pattern analysis"""
        if user_id not in self.user_violations:
            self.user_violations[user_id] = []
        
        violation = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': result.action.value,
            'confidence': result.confidence,
            'reasons': result.reasons
        }
        
        self.user_violations[user_id].append(violation)
        
        # Keep only recent violations (last 50 per user)
        if len(self.user_violations[user_id]) > 50:
            self.user_violations[user_id] = self.user_violations[user_id][-50:]
    
    def get_user_moderation_status(self, user_id: str) -> Dict:
        """Get moderation status for a user"""
        violations = self.user_violations.get(user_id, [])
        
        # Count violations by type in last 24 hours
        recent_violations = [
            v for v in violations 
            if (datetime.now(timezone.utc) - datetime.fromisoformat(v['timestamp'])).days < 1
        ]
        
        warning_count = len([v for v in recent_violations if v['action'] == 'warn'])
        block_count = len([v for v in recent_violations if v['action'] == 'block'])
        review_count = len([v for v in recent_violations if v['action'] == 'review'])
        
        # Determine user status
        status = "good"
        if (warning_count >= self.violation_thresholds['warnings'] or
            block_count >= self.violation_thresholds['blocks'] or
            review_count >= self.violation_thresholds['reviews']):
            status = "flagged"
        
        return {
            'user_id': user_id,
            'status': status,
            'recent_violations': {
                'warnings': warning_count,
                'blocks': block_count,
                'reviews': review_count
            },
            'total_violations': len(violations),
            'last_violation': violations[-1]['timestamp'] if violations else None
        }
    
    def get_moderation_stats(self) -> Dict:
        """Get overall moderation statistics"""
        if not self.moderation_log:
            return {'total_actions': 0}
        
        total_actions = len(self.moderation_log)
        actions_by_type = {}
        categories_by_type = {}
        
        for entry in self.moderation_log:
            action = entry['action']
            category = entry['category']
            
            actions_by_type[action] = actions_by_type.get(action, 0) + 1
            categories_by_type[category] = categories_by_type.get(category, 0) + 1
        
        return {
            'total_actions': total_actions,
            'actions_by_type': actions_by_type,
            'categories_by_type': categories_by_type,
            'flagged_users': len([uid for uid, violations in self.user_violations.items() 
                                if len(violations) >= 3])
        }

class SecurityHeadersManager:
    """Manages security headers for HTTP responses"""
    
    def __init__(self):
        self.default_headers = {
            # Prevent MIME type sniffing
            'X-Content-Type-Options': 'nosniff',
            
            # Prevent clickjacking
            'X-Frame-Options': 'DENY',
            
            # XSS protection (legacy but still useful)
            'X-XSS-Protection': '1; mode=block',
            
            # HSTS (HTTPS enforcement)
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            
            # Referrer policy
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            
            # Permissions policy (formerly Feature Policy)
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=()',
            
            # Content Security Policy (basic)
            'Content-Security-Policy': self._build_csp_header(),
            
            # Cross-Origin policies
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin'
        }
    
    def _build_csp_header(self) -> str:
        """Build Content Security Policy header"""
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://www.google.com https://www.gstatic.com",  # For reCAPTCHA
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",  # Allow images from CDN
            "connect-src 'self' https://api.comicguess.com",  # API endpoints
            "frame-src https://www.google.com",  # For reCAPTCHA
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "upgrade-insecure-requests"
        ]
        
        return "; ".join(csp_directives)
    
    def get_security_headers(self, request_path: str = None, 
                           additional_headers: Dict[str, str] = None) -> Dict[str, str]:
        """Get security headers for a response"""
        headers = self.default_headers.copy()
        
        # Path-specific header modifications
        if request_path:
            if request_path.startswith('/api/'):
                # API endpoints don't need some browser security headers
                headers.pop('X-Frame-Options', None)
                # More restrictive CSP for API
                headers['Content-Security-Policy'] = "default-src 'none'"
            
            elif request_path.startswith('/images/'):
                # Image endpoints
                headers['Cache-Control'] = 'public, max-age=31536000, immutable'
                headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
        
        # Add any additional headers
        if additional_headers:
            headers.update(additional_headers)
        
        return headers
    
    def validate_csp_compliance(self, content: str) -> List[str]:
        """Validate content against CSP policy"""
        violations = []
        
        # Check for inline scripts
        if re.search(r'<script[^>]*>(?!.*src=)', content, re.IGNORECASE):
            violations.append("Inline script detected (CSP violation)")
        
        # Check for inline styles
        if re.search(r'style\s*=\s*["\']', content, re.IGNORECASE):
            violations.append("Inline style detected (CSP violation)")
        
        # Check for javascript: URLs
        if re.search(r'javascript:', content, re.IGNORECASE):
            violations.append("JavaScript URL detected (CSP violation)")
        
        # Check for data: URLs in scripts
        if re.search(r'src\s*=\s*["\']data:', content, re.IGNORECASE):
            violations.append("Data URL in script source (CSP violation)")
        
        return violations

# Global instances
content_moderator = ContentModerationManager()
security_headers = SecurityHeadersManager()

# Convenience functions
def moderate_username(username: str, user_id: str = None) -> ModerationResult:
    """Moderate a username"""
    return content_moderator.moderate_content(username, ContentCategory.USERNAME, user_id)

def moderate_guess(guess: str, user_id: str = None, context: Dict = None) -> ModerationResult:
    """Moderate a character guess"""
    return content_moderator.moderate_content(guess, ContentCategory.GUESS, user_id, context)

def get_security_headers_for_response(request_path: str = None) -> Dict[str, str]:
    """Get security headers for HTTP response"""
    return security_headers.get_security_headers(request_path)