# Views - UI and API endpoints
from .api import app

# Dashboard lazy loaded to avoid import errors in API mode
def get_dashboard():
    from .dashboard import GRADIO_APP
    return GRADIO_APP