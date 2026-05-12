# api/routers/execute.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.transport.routers.execute instead

from backend.transport.routers.execute import router

__all__ = ["router"]
    return True


# ===================== EXECUTE =====================
class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30
    args: Optional[str] = None
    env: Optional[dict] = None
    run_validation: bool = False


class ExecuteResponse(BaseModel):
    result: str
    status: str = "ok"
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    errors: List[str] = []
    warnings: List[str] = []


@router.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """Execute Python code in sandbox"""
    import tempfile
    start = time.time()
    logger.info(f"[EXECUTE] received code: {request.code[:50]}...")
    
    try:
        if request.language == "python":
            from core.executor import CodeExecutor
            executor = CodeExecutor(timeout=request.timeout)
            
            main_file = Path(__file__).parent.parent / "main.py"
            cmd = ["python", str(main_file)]
            if request.args:
                cmd.extend(shlex.split(request.args))
                logger.info(f"[EXECUTE] running command: {' '.join(cmd)}")
            
            result = executor.run(
                code=request.code,
                args=request.args or "",
            )
            
            logger.info(f"[EXECUTE] result keys: {result.keys()}")
            logger.info(f"[EXECUTE] stdout: {repr(result.get('stdout', ''))}")
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
                            warnings.append("Bare 'except:' clause caught. Consider specifying exception types.")
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name):
                                if node.func.id == 'print':
                                    warnings.append("print() statement detected.")
                                elif node.func.id in ('eval', 'exec'):
                                    warnings.append(f"Potential security issue: {node.func.id}()")
                except SyntaxError as e:
                    errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
            
            return ExecuteResponse(
                result=result.get("stdout", ""),
                status="ok" if result.get("success", True) else "error",
                error=result.get("stderr") or result.get("error"),
                execution_time_ms=(time.time() - start) * 1000,
                errors=errors,
                warnings=warnings
            )
        else:
            return ExecuteResponse(
                result="",
                status="error",
                error=f"Language not supported: {request.language}",
                execution_time_ms=(time.time() - start) * 1000
            )
    except Exception as e:
        logger.error(f"Execute error: {e}")
        return ExecuteResponse(
            result="",
            status="error",
            error=str(e),
            execution_time_ms=(time.time() - start) * 1000
        )


# ===================== VALIDATE =====================
class ValidateRequest(BaseModel):
    code: str
    language: str = "python"


class ValidateResponse(BaseModel):
    errors: List[str] = []
    warnings: List[str] = []
    status: str = "ok"
    error: Optional[str] = None


@router.post("/validate", response_model=ValidateResponse)
async def validate(request: ValidateRequest):
    """Analyze Python code for errors and warnings without execution"""
    logger.info(f"[VALIDATE] analyzing code...")
    
    try:
        if request.language == "python":
            import ast
            
            errors: List[str] = []
            warnings: List[str] = []
            
            try:
                tree = ast.parse(request.code)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        if node.type is None:
                            warnings.append("Bare 'except:' clause caught. Consider specifying exception types.")
                    
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == 'print':
                            warnings.append("print() statement detected. Consider using a logging module instead.")
                    
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec'):
                            warnings.append(f"Potential security issue: {node.func.id}() can be dangerous.")
                    
            except SyntaxError as e:
                errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
            
            import py_compile
            try:
                py_compile.compile(request.code, '<string>', doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"Compilation error: {str(e)}")
            
            return ValidateResponse(
                errors=errors,
                warnings=warnings,
                status="ok"
            )
        else:
            return ValidateResponse(
                status="error",
                error=f"Language not supported: {request.language}"
            )
            
    except Exception as e:
        logger.error(f"Validate error: {e}")
        return ValidateResponse(
            status="error",
            error=str(e)
        )


# ===================== INSTALL DEPENDENCIES =====================
class InstallDepsRequest(BaseModel):
    code: str


class InstallDepsResponse(BaseModel):
    status: str = "ok"
    message: Optional[str] = None
    installed: Optional[List[str]] = None
    missing: Optional[List[str]] = None
    error: Optional[str] = None


@router.post("/install-deps", response_model=InstallDepsResponse)
async def install_deps(request: InstallDepsRequest):
    """Parse imports and auto-install missing packages"""
    logger.info(f"[INSTALL-DEPS] analyzing code...")
    
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
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except SyntaxError:
            return InstallDepsResponse(status="error", error="Invalid Python syntax")
        
        # Filter out standard library modules
        stdlib = {'os', 'sys', 'json', 're', 'math', 'time', 'datetime', 'random', 'collections', 
                 'itertools', 'functools', 'operator', 'string', 'io', 'logging', 'typing'}
        external = [imp for imp in imports if imp not in stdlib and not imp.startswith('_')]
        
        if not external:
            return InstallDepsResponse(
                status="ok",
                message="No external dependencies found",
                installed=[]
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
                installed=installed
            )
        
        # Install missing packages
        logger.info(f"[INSTALL-DEPS] Installing: {missing}")
        install_results = []
        for pkg in missing:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                install_results.append(pkg)
                logger.info(f"[INSTALL-DEPS] Installed: {pkg}")
            except Exception as e:
                logger.warning(f"[INSTALL-DEPS] Failed to install {pkg}: {e}")
        
        return InstallDepsResponse(
            status="ok",
            message=f"Installed {len(install_results)} package(s)",
            installed=install_results,
            missing=[p for p in missing if p not in install_results]
        )
        
    except Exception as e:
        logger.error(f"Install deps error: {e}")
        return InstallDepsResponse(status="error", error=str(e))