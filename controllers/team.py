import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from views.logger import get_logger

from models.settings import settings
WORKSPACE = settings.workspace

logger = get_logger(__name__)

# Import real agents from llm package
try:
    from llm import planner, architect, coder, debugger, reviewer, tester, devops, research as researcher
except ImportError as e:
    logger.warning(f"Failed to import real agents, using fallback: {e}")
    # Fallback to mock agents if llm import fails
    from unittest.mock import MagicMock
    
    def mock_agent_factory(name):
        agent_fn = MagicMock()
        agent_fn.return_value = f"[{name}] Mock response"
        return agent_fn
    
    planner = mock_agent_factory("planner")
    architect = mock_agent_factory("architect")
    coder = mock_agent_factory("coder")
    debugger = mock_agent_factory("debugger")
    reviewer = mock_agent_factory("reviewer")
    tester = mock_agent_factory("tester")
    devops = mock_agent_factory("devops")
    researcher = mock_agent_factory("researcher")

def save_file(name, content):
    """DEPRECATED - Legacy file save function. Use executor instead."""
    import tempfile
    from pathlib import Path
    
    workspace = Path(WORKSPACE)
    # Create temp file in workspace
    tmp_file = workspace / f"{name}.tmp"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file.write_text(content, encoding="utf-8")
    
    logger.warning("Legacy save_file called - consider migrating to CodeExecutor")
    return str(tmp_file)

def run():
    with open(f"{WORKSPACE}/app.py", "r", encoding="utf-8") as f:
        return f.read(), ""

def search_memory(task):
    """Search memory for context - placeholder for FAISS integration"""
    return []

def add_memory(*args):
    """Add to memory - placeholder for FAISS integration"""
    # TODO: Implement FAISS memory integration
    pass  # noqa: TODO

def run_team(task):
    try:
        logger.info("PLANNER: starting task=%s", task)
        plan = planner(task)
        logger.info("PLANNER: plan=%s", plan)

        memory_context = "\n".join(search_memory(task))
        logger.info("PLANNER: memory_context_len=%d", len(memory_context))

        logger.info("ARCHITECT: starting with task+context")
        arch = architect(task + memory_context)
        logger.info("ARCHITECT: arch=%s", arch)

        logger.info("CODER: generating code with arch context")
        code = coder(task + arch)
        save_file("app.py", code)

        for i in range(5):
            logger.info("RUNNER: iteration %d start", i+1)
            print(f"\n⚡ Iteration {i+1}")

            out, err = run()

            if err:
                logger.warning("RUNNER: iteration %d encountered error", i+1)
                print("🐞 Debugger...")
                code = debugger(code, err)
                save_file("app.py", code)
                add_memory(err)
                logger.info("RUNNER: iteration %d after debugger engaged", i+1)
            else:
                logger.info("RUNNER: iteration %d succeeded", i+1)
                print("🔍 Reviewer...")
                code = reviewer(code)
                save_file("app.py", code)

                print("🧪 Tester...")
                tests = tester(code)
                save_file("test_app.py", tests)

                print("🚀 DevOps...")
                docker = devops(code)
                save_file("Dockerfile", docker)

                add_memory(task)
                add_memory(code)

                logger.info("PLATFORM: DONE on iteration %d", i+1)
                print("✅ Done!")
                break
    except Exception as e:
        logger.error("Unhandled exception in run_team: %s", str(e), exc_info=True)
