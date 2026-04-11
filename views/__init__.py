# Views - UI and API endpoints
# Lazy loaded to avoid importing Gradio in API-only mode

def get_api():
    from api.main import app as api_app
    return api_app