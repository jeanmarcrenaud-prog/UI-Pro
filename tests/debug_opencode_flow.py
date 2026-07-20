import asyncio
import logging
import sys

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)

from backend.application.editor_manager import (
    init_editor_services, 
    get_editor_service, 
    get_opencode_manager
)

async def test_flow():
    # Initialisation des services
    ws_uri = "ws://localhost:8000"
    print(f"--- Initialisation des services sur {ws_uri} ---")
    await init_editor_services(ws_uri)
    
    # Récupération des instances
    editor_service = get_editor_service()
    manager = get_opencode_manager()

    # Mock du client pour intercepter l'action
    class MockClient:
        async def send_action(self, action):
            print(f"\n[TEST SUCCESS] Action envoyée au connecteur : {action}\n")
        async def connect(self):
            print("[Mock] Connexion établie.")
        async def close(self):
            print("[Mock] Connexion fermée.")

    # On injecte le client mocké
    manager.client = MockClient()
    manager.set_editor_update_callback(lambda x: None)

    print("\n--- Test d'envoi d'action (rename_file) ---")
    # On teste une action simple
    await manager.send_action('rename_file', {
        'current_path': '/path/to/old_file.py', 
        'new_name': 'new_file_name.py'
    })

if __name__ == "__main__":
    try:
        asyncio.run(test_flow())
    except Exception as e:
        print(f"Erreur lors du test : {e}")
        import traceback
        traceback.print_exc()
