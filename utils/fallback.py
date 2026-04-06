# 🛡️ **Fallback System** (Error Handling + Circuit Breaker)
#
# ✅ Fallback pour LLM échec
# ✅ Retry avec backoff
# ✅ Circuit breaker pattern
# ✅ Graceful degradation

from typing import Optional, Callable, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
import logging
import asyncio

logger = logging.getLogger(__name__)


# ==================== **1. CONFIGURATION** ====================

@dataclass
class FallbackConfig:
    """Configuration fallback"""
    # Retry logic
    max_retries: int = 3
    initial_retry_delay: float = 2.0  # secondes
    max_retry_delay: float = 60.0
    
    # Circuit breaker
    failure_threshold: int = 5
    reset_timeout: float = 300  # 5 minutes
    
    # Fallback models (priorité)
    fallback_models: List[str] = None
    
# Singleton
_CONFIG = FallbackConfig or ()
fallback_models = ["qwen2.5:7b", "qwen-opus", "small-cap"]


# ==================== **2. FALLBACK WRAPPER** ====================

class FallbackDecorator:
    """
    Decorateur pour wrapper LLM calls avec fallback.
    
    Usage :
      @fallback
      async def risky_call(prompt):
          return llm.generate(prompt)
    """
    
    def __init__(self, config: FallbackConfig = None):
        self.config = config or _CONFIG
        self._failure_counts: dict = {}
        self._last_failures: dict = {}
        
    def __call__(self, func: Callable) -> Callable:
        """
        Wrapper fonction avec fallback.
        """
        async def wrapper(*args, **kwargs) -> Any:
            try:
                result = await func(*args, **kwargs)
                
                # Reset circuit breaker on success
                key = str(args) + str(kwargs)
                if key in self._failure_counts:
                    self._failure_counts[key] = 0
                    self._last_failures[key] = None
                    
                return result
                
            except Exception as e:
                logger.warning(f"Call failed: {e}, trying fallback...")
                
                # Increment failure count
                key = str(args) + str(kwargs)
                self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
                
                # Circuit opened?
                if self._failure_counts[key] >= self.config.failure_threshold:
                    logger.error(f"Circuit breaker opened for {key}")
                    raise
                    
                # Retry with backoff
                if self._failure_counts[key] <= self.config.max_retries:
                    delay = min(
                        self.config.initial_retry_delay * (2 ** (self._failure_counts[key] - 1)),
                        self.config.max_retry_delay
                    )
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    
                    return await wrapper(*args, **kwargs)
                
                # Fallback model
                return self._fallback_call(key, e)
        
        return wrapper


# ==================== **3. FALLBACK CALL** ====================

class FallbackCall:
    """
    Système de fallback multi-modèle.
    
    Fallback chain:
      1. Try original model
      2. Try fallback model 1 (7b)
      3. Try fallback model 2 (opus)
      4. Return fallback text
    """
    
    def __init__(self, settings=None):
        from llm_client import OllamaClient
        from settings import Settings
        
        self.settings = settings or Settings()
        self.llms = [
            OllamaClient(self.settings),  # Original
            OllamaClient(self.settings),  # Fallback 1
            OllamaClient(self.settings),  # Fallback 2
        ]
        
    async def call(self, prompt: str, model: str = None) -> str:
        """
        Appeler LLM avec fallback.
        
        Args:
            prompt: Prompt LLM
            model: Modèle à utiliser
            
        Returns:
            Response ou fallback message
        """
        # Try original chain
        for llm in self.llms:
            result = await self._safe_generate(llm, prompt, model)
            if result and result != "ERROR":
                return result
        
        # Fallback to predefined text
        logger.warning("All LLMs failed. Returning fallback text.")
        return self._default_fallback(prompt)
    
    async def _safe_generate(self, llm, prompt: str, model: str = None) -> str:
        """
        Générer avec timeout + error handling.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            
            # Run blocking call in executor (Ollama API)
            response = await loop.run_in_executor(
                None,
                lambda: llm.generate(prompt, model or "qwen2.5:7b")
            )
            
            return response if response else "No response"
            
        except asyncio.TimeoutError:
            logger.error("Timeout error")
            raise TimeoutError(f"Ollama timeout: {self.settings.ollama_timeout}s")
            
        except Exception as e:
            logger.error(f"API error: {e}")
            return "ERROR"
    
    def _default_fallback(self, prompt: str) -> str:
        """
        Fallback text par défaut.
        """
        import json
        
        return f"""
[FAVOR FALLBACK TEXT]

Reason: Cannot access LLM

Prompt: {prompt[:100]}...

Fallback response:
- Analyzed task
- Plan steps
- Estimated time
"""


# ==================== **4. CIRCUIT BREAKER** ====================

class CircuitBreaker:
    """
    Circuit breaker pattern pour éviter cascading failures.
    
    States:
      - CLOSED: Normal (permettre calls)
      - OPEN: Failed (refuser calls)
      - HALF-OPEN: Testing (1 call autorisé)
    
    Usage :
      cb = CircuitBreaker(threshold=5, timeout=300)
      await cb.call("task")
    """
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        
        self._failure_counts: dict = {}
        self._last_failures: dict = {}
        self._state: dict = {}
    
    async def call(self, key: str, coro: Callable) -> Any:
        """
        Appeler avec circuit breaker.
        
        Args:
            key: Identifier pour tracking
            coro: Coroutine à appeler
            
        Returns:
            Resultat ou CircuitOpenException
        """
        state = self._get_state(key)
        
        if state == "OPEN":
            # Check reset timeout
            elapsed = time.time() - self._last_failures[key]
            if elapsed > self.reset_timeout:
                self._set_state(key, "HALF-OPEN")
                logger.info(f"Circuit half-open for {key}")
            else:
                logger.warning(f"Circuit open, refusing call: {key}")
                return self._circuit_open_response()
        
        # Try call
        try:
            result = await coro()
            self._set_state(key, "CLOSED")
            return result
            
        except Exception as e:
            self._set_state(key, "OPEN")
            logger.error(f"Circuit open after failure: {e}")
            raise CircuitOpenException(f"Circuit breaker open: {key}")
    
    def _get_state(self, key: str) -> str:
        return self._state.get(key, "CLOSED")
    
    def _set_state(self, key: str, state: str):
        self._state[key] = state
        
        if state == "OPEN":
            self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
            self._last_failures[key] = time.time()
        elif state == "HALF-OPEN" or state == "CLOSED":
            self._failure_counts[key] = 0
            
    def _circuit_open_response(self) -> str:
        """Response when circuit is open"""
        return "Circuit breaker: LLM unavailable"


class CircuitOpenException(Exception):
    """Exception circuit breaker"""
    pass


# ==================== **5. RAYONNEUR RATE LIMIT** ====================

class RateLimiter:
    """
    Rate limiter pour éviter rate limits API.
    
    Usage :
      limiter = RateLimiter(rate=5, window=60)  # 5 calls/min
      await limiter.call("task")
    """
    
    def __init__(self, rate: int = 5, window: int = 60):
        self.rate = rate
        self.window = window
        self._timestamps: List[float] = []
        
    async def call(self, coro: Callable) -> Any:
        """
        Appeler avec rate limiting.
        """
        now = time.time()
        
        # Clean old timestamps
        self._timestamps = [t for t in self._timestamps if now - t < self.window]
        
        # Check rate limit
        if len(self._timestamps) >= self.rate:
            wait_time = self.window - (now - self._timestamps[0])
            logger.info(f"Rate limited, waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
        
        # Call
        result = await coro()
        self._timestamps.append(now)
        
        return result


# ==================== **6. TEST SUITE** ====================

class TestFallbackSystem:
    def test_circuit_breaker(self):
        """Test circuit breaker"""
        cb = CircuitBreaker(threshold=3, timeout=60)
        
        # Call
        try:
            result = await cb.call("test", lambda: 5)
            assert result == 5
        except CircuitOpenException:
            assert "Circuit breaker" in str(result)
    
    def test_rate_limiter(self):
        """Test rate limiter"""
        limiter = RateLimiter(rate=2, window=60)
        
        # Call
        result = await limiter.call(lambda: 1)
        assert result == 1
pass
