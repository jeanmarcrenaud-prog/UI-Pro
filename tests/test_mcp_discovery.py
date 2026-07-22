import requests
import sys
import os

def test_mcp_discovery():
    # URL du serveur local
    BASE_URL = "http://localhost:8000"
    TOOLS_ENDPOINT = f"{BASE_URL}/mcp/tools"
    
    print(f"--- Test de découverte MCP ---")
    print(f"Tentative de connexion à : {TOOLS_ENDPOINT}")
    
    try:
        response = requests.get(TOOLS_ENDPOINT, timeout=5)
        print(f"Statut de la réponse : {response.status_code}")
        
        if response.status_code == 200:
            tools = response.json()
            print(f"Outils détectés ({len(tools)} au total) :")
            for tool in tools:
                print(f"  - {tool['name']} : {tool['description']}")
            
            # Vérification des outils critiques
            critical_tools = ["execute_intent", "generate_plan", "get_opencode_status"]
            missing = [t for t in critical_tools if t not in [tool['name'] for tool in tools]]
            
            if not missing:
                print("\n✅ SUCCESS : Tous les outils critiques sont exposés.")
                sys.exit(0)
            else:
                print(f"\n⚠️  WARNING : Les outils suivants sont manquants : {missing}")
                sys.exit(1)
        else:
            print(f"❌ ERREUR : Le serveur a répondu avec le code {response.status_code}")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print("❌ ERREUR : Impossible de se connecter au serveur.")
        print("Assurez-vous que le serveur backend tourne sur le port 8000.")
        print("Commande : uvicorn backend.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERREUR inattendue : {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_mcp_discovery()
