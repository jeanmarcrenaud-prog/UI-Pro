# services/chat_service.py - Chat Orchestration Service
"""
ChatService - Orchestrate LLM + memory + tools for a chat turn.

Contract:
    async run_chat(message: str, context?: dict) -> AsyncIterator[ChatEvent] | ChatResponse
    
    - Orchestrates LLM generation, memory retrieval, tool calls
    - Returns streaming events or final response
    - Handles retry on failure (max 3)
    
Dependencies:
    - LLM via llm/router.py
    - Memory via services/memory_service.py
    - Tools via services/tools.py
"""

import asyncio
import logging
import time
import json
from typing import Optional, Dict, Any, AsyncIterator, List
from datetime import datetime

from .base import BaseService, ServiceMetrics
from .model_service import get_model_service, ModelService
from .memory_service import get_memory_service, MemoryService
from .streaming import StreamChunk, StreamStatus
from .error_handler import get_error_handler
from .tools import get_tool_registry, ToolCall
from .agents import get_agent, Agent


class ChatService(BaseService):
    """
    Service d'orchestration des conversations.
    
    Gère le pipeline complet:
    1. Retrieval (memory context)
    2. Planning (LLM)
    3. Architecture (LLM)
    4. Code (LLM)
    5. Review (LLM)
    6. Execute (sandbox)
    
    Features:
    - Streaming throughout the chain
    - Automatic fallback on errors
    - Retry logic
    """
    
    def __init__(
        self, 
        model_service: ModelService = None, 
        memory_service: MemoryService = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        tool_registry = None,
        agent_name: str = None
    ):
        super().__init__("ChatService")
        self.model_service = model_service or get_model_service()
        self.memory_service = memory_service or get_memory_service()
        self.service_metrics = ServiceMetrics()
        
        # Retry configuration
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Error handler
        self._error_handler = get_error_handler()
        
        # Tool registry
        self.tool_registry = tool_registry or get_tool_registry()
        
        # Agent support
        self._agent = None
        if agent_name:
            self._agent = get_agent(agent_name, self.model_service, self.tool_registry)
        
        # Executor
        self._executor = None
    
    async def initialize(self) -> None:
        """Initialize chat service"""
        # Initialize model service
        await self.model_service.initialize()
        
        # Initialize memory service
        await self.memory_service.initialize()
        
        # Lazy load executor
        try:
            from controllers.executor import CodeExecutor
            self._executor = CodeExecutor()
        except Exception as e:
            self.logger.warning(f"Executor not available: {e}")
        
        self.logger.info("ChatService initialized")
    
    async def shutdown(self) -> None:
        """Shutdown chat service"""
        await self.model_service.shutdown()
        await self.memory_service.shutdown()
        self.logger.info("ChatService shutdown complete")
    
    async def execute(self, task: str) -> Dict[str, Any]:
        """
        Execute full pipeline for a task.
        
        Pipeline:
        1. Retrieve context from memory
        2. Plan → Architecture → Code → Review → Execute
        
        Args:
            task: User task description
            
        Returns:
            dict: Result with status, plan, architecture, code, tests, metrics
        """
        start_time = time.time()
        
        # Get context from memory
        context = self.memory_service.get_context(task, k=3)
        
        # Build system prompt with context
        system_context = f"Previous context:\n{context}\n\n" if context else ""
        
        try:
            # ===== STEP 1: PLANNING =====
            plan = await self._planner(task, system_context)
            
            # ===== STEP 2: ARCHITECTURE =====
            architecture = await self._architect(task, plan, system_context)
            
            # ===== STEP 3: CODE =====
            code = await self._coder(task, architecture, system_context)
            
            # ===== STEP 4: REVIEW =====
            review = await self._reviewer(code, system_context)
            
            # ===== STEP 5: EXECUTE =====
            execution = await self._execute(code)
            
            # Store successful execution in memory
            if execution.get("success"):
                memory_text = f"Task: {task[:100]}\nCode: {str(code)[:200]}"
                self.memory_service.add(memory_text)
            
            # Calculate metrics
            duration_ms = int((time.time() - start_time) * 1000)
            self.service_metrics.record_call(duration_ms, success=True)
            
            return {
                "status": "completed",
                "plan": plan,
                "architecture": architecture,
                "code": code,
                "review": review,
                "tests": execution,
                "metrics": {
                    "duration_ms": duration_ms,
                    "success": execution.get("success", False)
                }
            }
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.service_metrics.record_call(duration_ms, success=False)
            self.logger.error(f"Pipeline failed: {e}")
            
            return {
                "status": "failed",
                "error": str(e),
                "metrics": {
                    "duration_ms": duration_ms,
                    "success": False
                }
            }
    
    # ===== Pipeline Steps =====
    
    async def _planner(self, task: str, context: str = "") -> Dict:
        """Generate plan for task"""
        prompt = f"""{context}
You are a senior planner.

Return JSON:
{{
  "goal": "...",
  "steps": ["...", "..."]
}}

Task:
{task}
"""
        response = self.model_service.generate(prompt, mode="fast")
        return self._parse_json(response)
    
    async def _architect(self, task: str, plan: Dict, context: str = "") -> Dict:
        """Generate architecture from plan"""
        prompt = f"""{context}
You are a software architect.

Plan:
{json.dumps(plan)}

Return JSON:
{{
  "files": [
    {{"name": "main.py", "role": "..."}}
  ]
}}
"""
        response = self.model_service.generate(prompt, mode="reasoning")
        return self._parse_json(response)
    
    async def _coder(self, task: str, architecture: Dict, context: str = "") -> Dict:
        """Generate code from architecture"""
        prompt = f"""{context}
You are a senior Python engineer.

Architecture:
{json.dumps(architecture)}

Return JSON:
{{
  "files": {{
    "main.py": "code here"
  }}
}}
"""
        response = self.model_service.generate(prompt, mode="code")
        return self._parse_json(response)
    
    async def _reviewer(self, code: Dict, context: str = "") -> Dict:
        """Review generated code"""
        prompt = f"""{context}
Review this code and detect issues.

Code:
{json.dumps(code)}

Return JSON:
{{
  "issues": ["..."],
  "fixes": ["..."]
}}
"""
        response = self.model_service.generate(prompt, mode="fast")
        return self._parse_json(response)
    
    async def _execute(self, code: Dict) -> Dict:
        """Execute code in sandbox"""
        if not self._executor:
            return {"success": False, "error": "Executor not available"}
        
        # Run in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._executor.run,
            code.get("files", {})
        )
        
        # Auto-fix loop
        if not result.get("success"):
            result = await self._auto_fix(code, result)
        
        return result
    
    async def _auto_fix(self, code: Dict, execution_result: Dict) -> Dict:
        """Auto-fix loop (max 3 attempts)"""
        max_retry = 3
        attempt = 0
        current_code = code
        
        while attempt < max_retry:
            attempt += 1
            
            # Generate fix prompt
            error = execution_result.get("stderr", "")
            code_content = current_code.get("files", {}).get("main.py", "")
            
            fix_prompt = f"""Fix this Python code.

Error:
{error}

Current code:
{code_content}

Return ONLY JSON:
{{
  "files": {{
    "main.py": "fixed code here"
  }}
}}

Retry: {attempt}/{max_retry}
"""
            # Get fix from model
            fixed = self.model_service.generate(fix_prompt, mode="code")
            current_code = self._parse_json(fixed)
            
            # Try execution again
            loop = asyncio.get_event_loop()
            execution_result = await loop.run_in_executor(
                None,
                self._executor.run,
                current_code.get("files", {})
            )
            
            if execution_result.get("success"):
                return execution_result
        
        return execution_result
    
    def _parse_json(self, text: str) -> Dict:
        """Safely parse JSON from LLM response"""
        try:
            return json.loads(text)
        except:
            return {"raw": text, "error": "invalid_json"}
    
    def get_metrics(self) -> dict:
        """Get service metrics"""
        return {
            "service": "ChatService",
            "calls": self.service_metrics.total_calls,
            "success_rate": self.service_metrics.success_rate,
            "avg_latency_ms": self.service_metrics.avg_latency_ms,
            "model_service": self.model_service.get_metrics(),
            "memory_service": self.memory_service.get_metrics(),
        }
    
    # ===== Streaming Support =====
    
    async def execute_stream(
        self, 
        task: str,
        on_chunk: callable = None
    ) -> AsyncIterator[str]:
        """
        Execute pipeline with streaming response.
        
        Yields:
            str: Chunks of the response as they're generated
        """
        start_time = time.time()
        
        # Get context from memory
        context = self.memory_service.get_context(task, k=3)
        system_context = f"Previous context:\n{context}\n\n" if context else ""
        
        try:
            # Stream through pipeline steps
            # Step 1: Planning
            yield "📋 Planning...\n"
            plan = await self._planner(task, system_context)
            yield f"Plan: {json.dumps(plan, indent=2)}\n\n"
            
            # Step 2: Architecture  
            yield "🏗️ Designing architecture...\n"
            architecture = await self._architect(task, plan, system_context)
            yield f"Architecture: {json.dumps(architecture, indent=2)}\n\n"
            
            # Step 3: Code
            yield "💻 Writing code...\n"
            code = await self._coder(task, architecture, system_context)
            code_str = json.dumps(code, indent=2)[:500]
            yield f"Code:\n{code_str}\n\n"
            
            # Step 4: Review
            yield "🔍 Reviewing...\n"
            review = await self._reviewer(code, system_context)
            yield f"Review: {json.dumps(review, indent=2)}\n\n"
            
            # Step 5: Execute
            yield "🧪 Executing...\n"
            execution = await self._execute(code)
            
            if execution.get("success"):
                yield f"✅ Success!\n"
                yield f"Output: {execution.get('stdout', '')[:200]}\n"
            else:
                yield f"❌ Failed: {execution.get('stderr', '')[:200]}\n"
            
            # Save to memory
            self.memory_service.add(f"Task: {task[:100]}\nCode: {str(code)[:200]}")
            
            duration_ms = int((time.time() - start_time) * 1000)
            yield f"\n⏱️ Duration: {duration_ms}ms"
            
        except Exception as e:
            yield f"\n❌ Error: {str(e)}"
    
    async def chat_stream(
        self,
        messages: list,
        on_chunk: callable = None
    ) -> AsyncIterator[str]:
        """
        Simple chat with streaming.
        
        Args:
            messages: [{"role": "user", "content": "..."}]
            on_chunk: Optional callback for each chunk
            
        Yields:
            str: Response chunks
        """
        # Get last user message
        last_msg = messages[-1] if messages else {}
        user_input = last_msg.get("content", "")
        
        # Get context from memory
        context = self.memory_service.get_context(user_input, k=5)
        
        # Build prompt
        prompt = f"Context:\n{context}\n\n" if context else ""
        prompt += f"User: {user_input}\n\nAssistant:"
        
        # Use streaming service
        from .streaming import get_streaming_service
        streaming = get_streaming_service()
        
        async for chunk in streaming.stream_generate(prompt, mode="fast"):
            if chunk.status == StreamStatus.GENERATING:
                if on_chunk:
                    on_chunk(chunk)
                yield chunk.text
    
    # ===== Retry Logic =====
    
    async def _with_retry(self, func, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
        
        # All retries failed
        raise last_error
    
    # ===== Tool & Agent Support =====
    
    async def execute_with_tools(
        self,
        task: str,
        use_tools: bool = True,
        max_tool_calls: int = 5
    ) -> Dict[str, Any]:
        """
        Execute task with tool support.
        
        Args:
            task: User task
            use_tools: Enable tool usage
            max_tool_calls: Maximum tool calls per execution
            
        Returns:
            dict: Result with tool_calls history
        """
        tool_calls_history = []
        
        # Initial LLM call with tool schemas
        prompt = f"""Task: {task}

Available tools:
{json.dumps(self.tool_registry.get_schemas(), indent=2)}

Respond with JSON:
{{
  "response": "your response",
  "tool_calls": [{{"name": "tool_name", "arguments": {{}}}}] (if needed)
}}
"""
        response = self.model_service.generate(prompt, mode="reasoning")
        
        # Parse response
        result = self._parse_json(response)
        
        # Execute tools if present
        if use_tools and result.get("tool_calls"):
            for tc in result["tool_calls"][:max_tool_calls]:
                tool_call = ToolCall(
                    id=f"call_{len(tool_calls_history)}",
                    name=tc.get("name", ""),
                    arguments=tc.get("arguments", {})
                )
                
                tool_result = await self.tool_registry.execute_call(tool_call)
                tool_calls_history.append({
                    "call": tool_call.__dict__,
                    "result": tool_result
                })
                
                # Add tool result to context for next iteration
                result["tool_results"] = tool_calls_history
        
        return {
            "response": result.get("response", response[:200]),
            "tool_calls": tool_calls_history,
            "raw": result
        }
    
    async def execute_with_agent(
        self,
        task: str,
        agent_name: str = "coder"
    ) -> Dict[str, Any]:
        """
        Execute task using an agent.
        
        Args:
            task: User task
            agent_name: Name of agent to use ("coder" or "analyzer")
            
        Returns:
            dict: Agent execution result
        """
        if not self._agent:
            # Create agent on-the-fly
            self._agent = get_agent(agent_name, self.model_service, self.tool_registry)
        
        # Get context for the agent
        context = self.memory_service.get_context(task, k=3)
        
        # Run agent
        result = await self._agent.run(task, {"context": context})
        
        return result
    
    def register_tool(self, tool) -> None:
        """Register a custom tool"""
        self.tool_registry.register(tool)
    
    def list_tools(self) -> List[str]:
        """List available tools"""
        return self.tool_registry.list_tools()


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get singleton ChatService"""
    global _chat_service
    if _chat_service is None:
        model_svc = get_model_service()
        memory_svc = get_memory_service()
        _chat_service = ChatService(model_svc, memory_svc)
    return _chat_service