# Monitoring — Prometheus + Grafana

## Metrics disponibles

Toutes les métriques sont exposées au format Prometheus via l'endpoint `/metrics` :

### GPU (NVML / pynvml) — support multi-GPU
| Métrique | Type | Labels | Description |
|---|---|---|---|
| `gpu_utilization_percent` | Gauge | `gpu` | Utilisation GPU (0-100%) |
| `gpu_memory_used_bytes` | Gauge | `gpu` | VRAM utilisée (bytes) |
| `gpu_memory_total_bytes` | Gauge | `gpu` | VRAM totale (bytes) |
| `gpu_temperature_celsius` | Gauge | `gpu` | Température GPU (°C) |

Chaque GPU est identifié par le label `gpu` (ex: `gpu="0"`, `gpu="1"`).
Les métriques système (CPU/RAM) n'ont pas de label.

### Système (psutil)
| Métrique | Type | Description |
|---|---|---|
| `cpu_percent` | Gauge | Utilisation CPU (%) |
| `memory_percent` | Gauge | Utilisation RAM (%) |

### LLM
| Métrique | Type | Labels | Description |
|---|---|---|---|
| `llm_request_latency_seconds` | Histogram | `provider`, `model_type` | Latence des appels LLM (buckets: 0.1s–600s) |
| `llm_errors_total` | Counter | `provider`, `error_type` | Erreurs LLM cumulées |
| `llm_active_requests` | Gauge | `provider` | Requêtes LLM en cours |
| `llm_tokens_total` | Counter | `provider` | Tokens générés cumulés |

## Sécurité

Si une `api_key` est configurée (via `API_KEY` env var ou `config.yaml`),
l'endpoint `/metrics` est protégé par le header `x-api-key` :

```bash
# Avec API key
curl -H "x-api-key: votre-cle" http://localhost:8000/metrics

# Sans API key (self-hosted, aucun changement)
curl http://localhost:8000/metrics
```

Prometheus peut être configuré avec le header :

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'ui-pro'
    scrape_interval: 5s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
    authorization:
      credentials: "votre-cle"
      type: Bearer  # ou omettez pour utiliser x-api-key
```

Ou via `params` si vous préférez (non recommandé) :

```yaml
    params:
      api_key: ['votre-cle']
```

## Dashboard Grafana

1. Importer `docs/monitoring/grafana-dashboard.json` dans Grafana
2. Ajouter une datasource Prometheus pointant vers votre instance Prometheus
3. Dashboard : **UI-Pro / System & LLM Monitoring**

### Panneaux du dashboard
- **System** : CPU, RAM, GPU Utilization, GPU Temperature (jauges)
- **GPU Memory** : VRAM used / total (timeseries)
- **LLM Telemetry** : Request Latency (p95/p50), Token Throughput, Error Rate, Active Requests

## Architecture

```
┌───────────────────┐     scrape (5s)     ┌────────────┐
│   FastAPI :8000   │ ──────────────────> │ Prometheus │
│   /metrics        │                     └─────┬──────┘
│                   │                           │
│  prometheus_client│                           │ query
│  CollectorRegistry│                           ▼
│                   │                     ┌──────────┐
│  - pynvml gauges  │                     │ Grafana  │
│  - psutil gauges  │                     │ :3000    │
│  - llm histograms │                     └──────────┘
└───────────────────┘
```

Les métriques sont mises à jour à chaque `scrape` (le endpoint `/metrics` appelle
`update_system_metrics()` avant de générer le texte Prometheus). Les métriques LLM
sont mises à jour en temps réel depuis `LLMWrapper` dans `llm_wrapper.py`.
