from dataclasses import dataclass
from typing import Optional, List

@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    is_final: bool
    start_time: float
    end_time: float

@dataclass
class AudioChunk:
    data: bytes
    sample_rate: int
    channel_count: int
