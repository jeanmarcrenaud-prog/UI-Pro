# Monitoring — Prometheus + Grafana

## Metrics disponibles

Toutes les métriques sont exposées au format Prometheus via l'endpoint `/metrics` :

### GPU (NVML / pynvml)
| Métrique | Type | Description |
|---|---|---|
| `gpu_utilization_percent` | Gauge | Utilisation GPU (0-100%) |
| `gpu_memory_used_bytes` | Gauge | VRAM utilisée (bytes) |
| `gpu_memory_total_bytes` | Gauge | VRAM totale (bytes) |
| `gpu_temperature_celsius` | Gauge | Température GPU (°C) |

### Système (psutil)
| Métrique | Type | Description |
|---|---|---|
| `cpu_percent` | Gauge | Utilisation CPU (%) |
| `memory_percent` | Gauge | Utilisation RAM (%) |

### LLM
| Métrique | Type | Labels | Description |
|---|---|---|---|
| `llm_request_latency_seconds` | Histogram | `provider`, `model_type` | Latence des appels LLM |
| `llm_errors_total` | Counter | `provider`, `error_type` | Erreurs LLM cumulées |
| `llm_active_requests` | Gauge | `provider` | Requêtes LLM en cours |
| `llm_tokens_total` | Counter | `provider` | Tokens générés cumulés |

## Configuration Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'ui-pro'
    scrape_interval: 5s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
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
