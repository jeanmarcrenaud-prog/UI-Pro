# Scripts

## Utility Scripts

| Script | Description |
|--------|-------------|
| `verify_imports.py` | Verify all imports point to backend/ |
| `check_cleanup.py` | Check for legacy imports |
| `kill_port.py` | Kill process on specific port |

## Usage

```bash
# Verify imports
python scripts/verify_imports.py

# Check cleanup
python scripts/check_cleanup.py

# Kill port 8000
python scripts/kill_port.py 8000
```