# services/model_service.py - Model Management Service
#
# Role: Intelligent model selection with latency/success tracking
# Used by: orchestrator, router fallback
# - Fallback automatique intelligent
# - Latency tracking (p50, p95)
# - Routing contextuel selon task + historique
# - Warm-up des modèles froids

import time
import logging
import threading
from typing import Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from statistics import median

from .base import BaseService, ServiceMetrics


@dataclass
class ModelConfig:
    """Configuration for a model"""
    name: str
    endpoint: str = "http://localhost:11434/api/generate"
    timeout: int = 60
    max_retries: int = 2
    is_fallback: bool = False
    # Advanced config
    max_latency_ms: float = 30000  # Exclude if too slow
    min_success_rate: float = 0.5  # Exclude if too many failures


@dataclass 
class LatencySnapshot:
    """Single latency measurement"""
    value_ms: float
    timestamp: datetime


@dataclass
class ModelMetrics:
    """Metrics per model with latency percentiles"""
    name: str
    total_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    last_used: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    # Latency tracking (keep last 100)
    _latency_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.failed_calls) / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls
    
    @property
    def p50_latency_ms(self) -> float:
        if not self._latency_history:
            return 0.0
        return median([s.value_ms for s in self._latency_history])
    
    @property
    def p95_latency_ms(self) -> float:
        if not self._latency_history:
            return 0.0
        sorted_latencies = sorted([s.value_ms for s in self._latency_history])
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    @property
    def is_cold(self) -> bool:
        """Model hasn't been used recently"""
        if self.last_used is None:
            return True
        return (datetime.now() - self.last_used) > timedelta(minutes=5)
    
    @property
    def is_recently_failed(self) -> bool:
        """Model failed recently (within last 30s)"""
        if self.last_failure is None:
            return False
        return (datetime.now() - self.last_failure) < timedelta(seconds=30)
    
    def record(self, latency_ms: float, success: bool) -> None:
        self.total_calls += 1
        if latency_ms > 0:
            self.total_latency_ms += latency_ms
            self._latency_history.append(LatencySnapshot(latency_ms, datetime.now()))
        if not success:
            self.failed_calls += 1
            self.last_failure = datetime.now()
        else:
            self.last_used = datetime.now()
    
    def reset_failure_status(self) -> None:
        """Reset failure status (allow retry after cooldown)"""
        self.last_failure = None


class ModelSelector:
    """
    Intelligent model selection based on:
    - Latency (exclude slow models)
    - Success rate (exclude unreliable models)
    - Recency (prefer recently used)
    - Task type matching
    """
    
    def __init__(self, models: dict, metrics: dict, config: dict):
        self.models = models
        self.metrics = metrics
        self.config = config
        
        # Task type to mode mapping
        self.task_mode_map = {
            "code": ["code", "implement", "function", "class ", "def ", "import "],
            "reasoning": ["debug", "error", "architect", "plan", "complex", "why ", "how "],
            "fast": ["explain", "describe", "what ", "who ", "simple", "list "],
        }
    
    def get_mode_for_task(self, task: str) -> str:
        """Determine best mode for task"""
        task_lower = task.lower()
        
        for mode, keywords in self.task_mode_map.items():
            if any(kw in task_lower for kw in keywords):
                return mode
        
        return "reasoning"  # Default
    
    def select_models(self, mode: str, context: dict = None) -> list[str]:
        """
        Select ordered list of models to try.
        
        Filters out:
        - Models with high latency (p95 > max_latency_ms)
        - Models with low success rate (< min_success_rate)
        - Models that recently failed (within 30s)
        """
        selected = []
        
        # Get primary model
        primary = self.models.get(mode)
        if not primary:
            mode = "fast"
            primary = self.models.get(mode)
        
        if not primary:
            return []
        
        # Start with primary
        candidates = [mode]
        
        # Add fallbacks
        fallback_chain = {
            "fast": ["reasoning"],
            "reasoning": ["fast"],
            "code": ["reasoning", "fast"],
        }
        
        for fb_mode in fallback_chain.get(mode, []):
            if fb_mode not in candidates:
                candidates.append(fb_mode)
        
        # Filter candidates
        for candidate_mode in candidates:
            model_config = self.models.get(candidate_mode)
            model_metrics = self.metrics.get(candidate_mode)
            
            if not model_config or not model_metrics:
                selected.append(candidate_mode)
                continue
            
            # Skip recently failed
            if model_metrics.is_recently_failed:
                self._log_skip(candidate_mode, "recently_failed")
                continue
            
            # Skip low success rate
            if model_metrics.success_rate < model_config.min_success_rate:
                self._log_skip(candidate_mode, f"low_success_rate={model_metrics.success_rate:.2f}")
                continue
            
            # Skip high latency (only if we have data)
            if model_metrics.total_calls > 5 and model_metrics.p95_latency_ms > model_config.max_latency_ms:
                self._log_skip(candidate_mode, f"high_latency_p95={model_metrics.p95_latency_ms:.0f}ms")
                continue
            
            selected.append(candidate_mode)
        
        return selected
    
    def _log_skip(self, mode: str, reason: str) -> None:
        logging.getLogger("services.model_selector").debug(f"Skipping {mode}: {reason}")


class ModelService(BaseService):
    """
    Service de gestion des modèles LLM.
    
    Advanced Features:
    - Latency-aware model selection (p50, p95)
    - Smart fallback based on success rate
    - Context-aware routing
    - Model warm-up (cold start avoidance)
    """
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__("ModelService")
        from models.settings import settings
        self.config = config or {}
        
        # Modèles disponibles - importés depuis settings
        self.models: dict[str, ModelConfig] = {
            "fast": ModelConfig(
                name=self.config.get("MODEL_FAST") or settings.model_fast,
                endpoint=self._build_endpoint(),
                max_latency_ms=self.config.get("MAX_LATENCY_MS", 30000),
                min_success_rate=self.config.get("MIN_SUCCESS_RATE", 0.5),
            ),
            "reasoning": ModelConfig(
                name=self.config.get("MODEL_REASONING") or settings.model_reasoning,
                endpoint=self._build_endpoint(),
                max_latency_ms=self.config.get("MAX_LATENCY_MS", 60000),
                min_success_rate=self.config.get("MIN_SUCCESS_RATE", 0.5),
            ),
            "code": ModelConfig(
                name=self.config.get("MODEL_CODE") or getattr(settings, 'model_code', 'deepseek-coder:33b'),
                endpoint=self._build_endpoint(),
                max_latency_ms=self.config.get("MAX_LATENCY_MS", 45000),
                min_success_rate=self.config.get("MIN_SUCCESS_RATE", 0.5),
            ),
        }
        
        # Metrics par modèle
        self.model_metrics: dict[str, ModelMetrics] = {
            name: ModelMetrics(name=config.name)
            for name, config in self.models.items()
        }
        
        # Service metrics
        self.service_metrics = ServiceMetrics()
        
        # Model selector (intelligent routing)
        self._selector = ModelSelector(self.models, self.model_metrics, self.config)
        
        # Warm-up lock
        self._warmup_lock = threading.Lock()
        self._warmup_done: set[str] = set()
        
        # Client LLM
        self._llm_client = None
    
    def _build_endpoint(self) -> str:
        base = self.config.get("OLLAMA_URL", "http://localhost:11434")
        if "/api/" not in base:
            return base.rstrip("/") + "/api/generate"
        return base
    
    async def initialize(self) -> None:
        """Initialize model service"""
        try:
            from adapters.llm import OllamaClient
            self._llm_client = OllamaClient()
            self.logger.info(f"ModelService initialized with models: {list(self.models.keys())}")
            
            # Warm up primary models in background
            await self._warmup_models()
            
        except Exception as e:
            self._set_error(str(e))
            raise
    
    async def _warmup_models(self) -> None:
        """Warm up models to avoid cold start"""
        def _do_warmup():
            with self._warmup_lock:
                for mode, model_config in self.models.items():
                    if model_config.name in self._warmup_done:
                        continue
                    
                    try:
                        # Quick warmup call
                        client = self._get_client_for_model(model_config)
                        client.generate("ok", model=model_config.name)
                        self._warmup_done.add(model_config.name)
                        logging.getLogger("services").info(f"Warmed up model: {model_config.name}")
                    except Exception as e:
                        logging.getLogger("services").warning(f"Warmup failed for {model_config.name}: {e}")
        
        # Run warmup in background thread (non-blocking)
        threading.Thread(target=_do_warmup, daemon=True).start()
    
    async def shutdown(self) -> None:
        """Shutdown model service"""
        self.logger.info("ModelService shutting down")
    
    def _get_client_for_model(self, model_config: ModelConfig):
        """Create LLM client for specific model"""
        from adapters.llm import OllamaClient
        
        class ModelConfigWrapper:
            def __init__(self, url: str, model: str):
                self.url = url
                self.model = model
        
        return OllamaClient(ModelConfigWrapper(model_config.endpoint, model_config.name))
    
    def generate(
        self,
        prompt: str,
        mode: str = "fast",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        task_hint: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 2
    ) -> str:
        """
        Generate response with intelligent fallback.
        
        Args:
            prompt: User prompt
            mode: Requested mode (fast, reasoning, code)
            system_prompt: Optional system prompt
            temperature: Generation temperature
            task_hint: Optional task description for smart routing
            timeout: Request timeout in seconds
            max_retries: Number of retries per model
            
        Returns:
            str: Generated response or error message
        """
        start_time = time.time()
        
        # Smart model selection
        context = {"task": task_hint} if task_hint else {}
        modes_to_try = self._selector.select_models(mode, context)
        
        if not modes_to_try:
            self.logger.warning(f"No models available for mode: {mode}")
            modes_to_try = ["fast"]  # Fallback
        
        last_error = None
        
        for try_mode in modes_to_try:
            model_config = self.models.get(try_mode)
            if not model_config:
                continue
            
            # Skip recently failed (check again in case of race condition)
            if self.model_metrics[try_mode].is_recently_failed:
                self.logger.debug(f"Skipping {try_mode} - recently failed")
                continue
            
            # Try with retries
            for attempt in range(max_retries):
                try:
                    self.logger.debug(f"Trying model {model_config.name} (attempt {attempt + 1})")
                    client = self._get_client_for_model(model_config)
                    
                    # Use timeout in client
                    original_timeout = getattr(client, 'timeout', 60)
                    client.timeout = timeout
                    
                    response = client.generate(
                        prompt, 
                        model=model_config.name, 
                        system_prompt=system_prompt, 
                        temperature=temperature
                    )
                    
                    # Restore timeout
                    client.timeout = original_timeout
                    
                    # Check for error response
                    if response.startswith("[ModelService Error") or response.startswith("[OllamaError"):
                        if attempt < max_retries - 1:
                            continue  # Retry
                    
                    # Record success
                    latency_ms = (time.time() - start_time) * 1000
                    self.model_metrics[try_mode].record(latency_ms, success=True)
                    self.service_metrics.record_call(latency_ms, success=True)
                    
                    # Clear failure status on success
                    self.model_metrics[try_mode].reset_failure_status()
                    
                    return response
                    
                except Exception as e:
                    last_error = str(e)
                    self.logger.warning(f"Model {model_config.name} attempt {attempt + 1} failed: {e}")
                    # Record failure
                    self.model_metrics[try_mode].record(0, success=False)
                    
                    # Don't retry on timeout
                    if "timeout" in last_error.lower():
                        break
        
        # All models failed
        latency_ms = (time.time() - start_time) * 1000
        self.service_metrics.record_call(latency_ms, success=False)
        self.logger.error(f"All models failed for mode {mode}: {last_error}")
        return f"[ModelService Error: All models failed - {last_error}]"
    
    async def generate_async(
        self,
        prompt: str,
        mode: str = "fast",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        task_hint: Optional[str] = None
    ) -> str:
        """Async wrapper for generate"""
        return self.generate(prompt, mode, system_prompt, temperature, task_hint)
    
    def get_metrics(self) -> dict:
        """Get detailed service metrics"""
        return {
            "service": "ModelService",
            "total_calls": self.service_metrics.total_calls,
            "success_rate": round(self.service_metrics.success_rate, 3),
            "avg_latency_ms": round(self.service_metrics.avg_latency_ms, 2),
            "models": {
                name: {
                    "total_calls": m.total_calls,
                    "failed_calls": m.failed_calls,
                    "success_rate": round(m.success_rate, 3),
                    "avg_latency_ms": round(m.avg_latency_ms, 2),
                    "p50_latency_ms": round(m.p50_latency_ms, 2),
                    "p95_latency_ms": round(m.p95_latency_ms, 2),
                    "is_cold": m.is_cold,
                    "is_recently_failed": m.is_recently_failed,
                    "last_used": m.last_used.isoformat() if m.last_used else None,
                }
                for name, m in self.model_metrics.items()
            }
        }
    
    def get_best_model(self, task_type: str = None) -> str:
        """Get best performing model for task type"""
        if task_type:
            mode = self._selector.get_mode_for_task(task_type)
        else:
            mode = "fast"
        
        # Find model with best success rate + lowest latency
        best = None
        best_score = -1
        
        for m in self.model_metrics.values():
            if m.total_calls < 3:  # Need some data
                continue
            
            # Score: success_rate * (1 / normalized_latency)
            latency_factor = 1.0 / (m.avg_latency_ms + 1)
            score = m.success_rate * latency_factor
            
            if score > best_score:
                best_score = score
                best = m.name
        
        return best or self.models.get(mode, ModelConfig(name="unknown")).name


# Singleton instance
_model_service: Optional[ModelService] = None


def get_model_service() -> ModelService:
    """Get singleton ModelService"""
    global _model_service
    if _model_service is None:
        try:
            from models.settings import Settings
            config = Settings().__dict__
        except:
            config = {}
        
        _model_service = ModelService(config)
    return _model_service