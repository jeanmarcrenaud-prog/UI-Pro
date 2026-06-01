# api/routers/execute.py - Execute, validate, install-deps endpoints
import logging
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel

from settings import settings

router = APIRouter(prefix="/api", tags=["execute"])

logger = logging.getLogger(__name__)

API_KEY_HEADER = "x-api-key"


def verify_api_key(request: Request):
    api_key = getattr(settings, "api_key", None)
    if not api_key:
        return True
    if request.headers.get(API_KEY_HEADER) != api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


# ===================== EXECUTE =====================
class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30
    args: str | None = None
    env: dict | None = None
    run_validation: bool = False


class ExecuteResponse(BaseModel):
    result: str
    status: str = "ok"
    error: str | None = None
    execution_time_ms: float = 0.0
    errors: list[str] = []
    warnings: list[str] = []


@router.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """Execute Python code in sandbox"""
    start = time.time()
    logger.info(f"[EXECUTE] received code: {request.code[:50]}...")

    try:
        if request.language == "python":
            from backend.domain.core.executor import CodeExecutor

            executor = CodeExecutor()

            result = executor.run(
                code=request.code,
                timeout=request.timeout,
            )

            logger.info(f"[EXECUTE] result keys: {result.keys()}")
            logger.info(f"[EXECUTE] stdout: {result.get('stdout', '')!r}")
            logger.info(f"[EXECUTE] success: {result.get('success')}")

            # Run validation if requested
            errors = []
            warnings = []
            if request.run_validation:
                import ast

                try:
                    tree = ast.parse(request.code)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ExceptHandler) and node.type is None:
                            warnings.append(
                                "Bare 'except:' clause caught. Consider specifying exception types."
                            )
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name):
                                if node.func.id == "print":
                                    warnings.append("print() statement detected.")
                                elif node.func.id in ("eval", "exec"):
                                    warnings.append(
                                        f"Potential security issue: {node.func.id}()"
                                    )
                except SyntaxError as e:
                    errors.append(f"Syntax error: {e.msg} at line {e.lineno}")

            return ExecuteResponse(
                result=result.get("stdout", ""),
                status="ok" if result.get("success", True) else "error",
                error=result.get("stderr") or result.get("error"),
                execution_time_ms=(time.time() - start) * 1000,
                errors=errors,
                warnings=warnings,
            )
        else:
            return ExecuteResponse(
                result="",
                status="error",
                error=f"Language not supported: {request.language}",
                execution_time_ms=(time.time() - start) * 1000,
            )
    except Exception as e:
        logger.error(f"Execute error: {e}")
        return ExecuteResponse(
            result="",
            status="error",
            error=str(e),
            execution_time_ms=(time.time() - start) * 1000,
        )


# ===================== VALIDATE =====================
class ValidateRequest(BaseModel):
    code: str
    language: str = "python"


class ValidateResponse(BaseModel):
    errors: list[str] = []
    warnings: list[str] = []
    status: str = "ok"
    error: str | None = None


@router.post("/validate", response_model=ValidateResponse)
async def validate(request: ValidateRequest):
    """Analyze Python code for errors and warnings without execution"""
    logger.info("[VALIDATE] analyzing code...")

    try:
        if request.language == "python":
            import ast

            errors: list[str] = []
            warnings: list[str] = []

            try:
                tree = ast.parse(request.code)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        if node.type is None:
                            warnings.append(
                                "Bare 'except:' clause caught. Consider specifying exception types."
                            )

                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "print":
                            warnings.append(
                                "print() statement detected. Consider using a logging module instead."
                            )

                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in (
                            "eval",
                            "exec",
                        ):
                            warnings.append(
                                f"Potential security issue: {node.func.id}() can be dangerous."
                            )

            except SyntaxError as e:
                errors.append(f"Syntax error: {e.msg} at line {e.lineno}")

            try:
                compile(request.code, '<string>', 'exec')
            except SyntaxError as e:
                errors.append(f"Compilation error: {e.msg} at line {e.lineno}")

            return ValidateResponse(errors=errors, warnings=warnings, status="ok")
        else:
            return ValidateResponse(
                status="error", error=f"Language not supported: {request.language}"
            )

    except Exception as e:
        logger.error(f"Validate error: {e}")
        return ValidateResponse(status="error", error=str(e))


# ===================== INSTALL DEPENDENCIES =====================
class InstallDepsRequest(BaseModel):
    code: str


class InstallDepsResponse(BaseModel):
    status: str = "ok"
    message: str | None = None
    installed: list[str] | None = None
    missing: list[str] | None = None
    error: str | None = None


@router.post("/install-deps", response_model=InstallDepsResponse)
async def install_deps(request: InstallDepsRequest):
    """Parse imports and auto-install missing packages"""
    logger.info("[INSTALL-DEPS] analyzing code...")

    try:
        import ast
        import subprocess
        import sys

        # Parse the code to extract imports
        imports = set()
        try:
            tree = ast.parse(request.code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split(".")[0])
        except SyntaxError:
            return InstallDepsResponse(status="error", error="Invalid Python syntax")

        # Filter out standard library modules
        stdlib = {
            "os",
            "sys",
            "json",
            "re",
            "math",
            "time",
            "datetime",
            "random",
            "collections",
            "itertools",
            "functools",
            "operator",
            "string",
            "io",
            "logging",
            "typing",
        }
        external = [
            imp for imp in imports if imp not in stdlib and not imp.startswith("_")
        ]

        if not external:
            return InstallDepsResponse(
                status="ok", message="No external dependencies found", installed=[]
            )

        # Check which are already installed
        missing = []
        installed = []
        for pkg in external:
            try:
                __import__(pkg)
                installed.append(pkg)
            except ImportError:
                missing.append(pkg)

        if not missing:
            return InstallDepsResponse(
                status="ok",
                message=f"All dependencies already installed: {', '.join(installed)}",
                installed=installed,
            )

        # Install missing packages
        logger.info(f"[INSTALL-DEPS] Installing: {missing}")
        install_results = []
        for pkg in missing:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                install_results.append(pkg)
                logger.info(f"[INSTALL-DEPS] Installed: {pkg}")
            except Exception as e:
                logger.warning(f"[INSTALL-DEPS] Failed to install {pkg}: {e}")

        return InstallDepsResponse(
            status="ok",
            message=f"Installed {len(install_results)} package(s)",
            installed=install_results,
            missing=[p for p in missing if p not in install_results],
        )

    except Exception as e:
        logger.error(f"Install deps error: {e}")
        return InstallDepsResponse(status="error", error=str(e))
