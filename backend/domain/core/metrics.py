"""
Metrics Module - Track execution statistics and persist to disk.
"""

import json
import os
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """Single execution record"""
    task_id: str
    task: str
    status: str  # "success", "failed", "timeout"
    duration_ms: int
    timestamp: str
    error: Optional[str] = None
    retries: int = 0


@dataclass
class Metrics:
    """Metrics aggregate data"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration_ms: int = 0
    avg_duration_ms: float = 0.0
    max_duration_ms: int = 0
    min_duration_ms: int = 0
    total_retries: int = 0


class MetricsManager:
    """Track and persist execution metrics"""
    
    def __init__(self, persist_path: str = "data/metrics.json"):
        self.persist_path = Path(persist_path)
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.records: List[ExecutionRecord] = []
        self._load()
    
    def _load(self):
        """Load metrics from disk"""
        if self.persist_path.exists():
            try:
                with open(self.persist_path, "r") as f:
                    data = json.load(f)
                    records_data = data.get("records", [])
                    self.records = [
                        ExecutionRecord(
                            task_id=r["task_id"],
                            task=r["task"],
                            status=r["status"],
                            duration_ms=r["duration_ms"],
                            timestamp=r["timestamp"],
                            error=r.get("error"),
                            retries=r.get("retries", 0),
                        )
                        for r in records_data
                    ]
                logger.info(f"Loaded {len(self.records)} metric records")
            except Exception as e:
                logger.warning(f"Failed to load metrics: {e}")
    
    def _save(self):
        """Save metrics to disk"""
        try:
            data = {
                "records": [
                    {
                        "task_id": r.task_id,
                        "task": r.task,
                        "status": r.status,
                        "duration_ms": r.duration_ms,
                        "timestamp": r.timestamp,
                        "error": r.error,
                        "retries": r.retries,
                    }
                    for r in self.records
                ],
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def record_execution(
        self,
        task_id: str,
        task: str,
        status: str,
        duration_ms: int,
        error: Optional[str] = None,
        retries: int = 0,
    ):
        """Record a single execution"""
        record = ExecutionRecord(
            task_id=task_id,
            task=task,
            status=status,
            duration_ms=duration_ms,
            timestamp=datetime.now().isoformat(),
            error=error,
            retries=retries,
        )
        self.records.append(record)
        self._save()
    
    def get_metrics(self) -> Metrics:
        """Calculate aggregate metrics"""
        if not self.records:
            return Metrics()
        
        successful = [r for r in self.records if r.status == "success"]
        failed = [r for r in self.records if r.status in ("failed", "timeout")]
        durations = [r.duration_ms for r in self.records]
        
        return Metrics(
            total_executions=len(self.records),
            successful_executions=len(successful),
            failed_executions=len(failed),
            total_duration_ms=sum(durations),
            avg_duration_ms=sum(durations) / len(durations) if durations else 0,
            max_duration_ms=max(durations) if durations else 0,
            min_duration_ms=min(durations) if durations else 0,
            total_retries=sum(r.retries for r in self.records),
        )
    
    def get_success_rate(self) -> float:
        """Get success rate percentage"""
        if not self.records:
            return 0.0
        successful = sum(1 for r in self.records if r.status == "success")
        return (successful / len(self.records)) * 100
    
    def get_recent_records(self, limit: int = 10) -> List[Dict]:
        """Get recent execution records"""
        records = self.records[-limit:]
        return [
            {
                "task_id": r.task_id,
                "task": r.task[:50] + "..." if len(r.task) > 50 else r.task,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "timestamp": r.timestamp,
            }
            for r in reversed(records)
        ]
    
    def rotate(self, max_records: int = 100):
        """Rotate logs, keeping only recent records"""
        if len(self.records) > max_records:
            self.records = self.records[-max_records:]
            self._save()
    
    def clear(self):
        """Clear all metrics"""
        self.records = []
        self._save()


# Singleton instance
_metrics_manager: Optional[MetricsManager] = None


def get_metrics_manager(persist_path: str = "data/metrics.json") -> MetricsManager:
    """Get singleton metrics manager"""
    global _metrics_manager
    if _metrics_manager is None:
        _metrics_manager = MetricsManager(persist_path=persist_path)
    return _metrics_manager


def record_execution(
    task_id: str,
    task: str,
    status: str,
    duration_ms: int,
    error: Optional[str] = None,
    retries: int = 0,
):
    """Convenience function to record execution"""
    get_metrics_manager().record_execution(
        task_id=task_id,
        task=task,
        status=status,
        duration_ms=duration_ms,
        error=error,
        retries=retries,
    )


def get_metrics() -> Metrics:
    """Get current metrics"""
    return get_metrics_manager().get_metrics()


def get_dashboard_data() -> Dict:
    """Get data formatted for dashboard display"""
    mgr = get_metrics_manager()
    metrics = mgr.get_metrics()
    
    return {
        "metrics": asdict(metrics),
        "success_rate": mgr.get_success_rate(),
        "recent": mgr.get_recent_records(limit=10),
    }