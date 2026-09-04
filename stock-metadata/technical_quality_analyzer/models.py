from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class Status(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    HIGH_RISK = "HIGH_RISK"
    ERROR = "ERROR"

@dataclass
class Anomaly:
    x_norm: float
    y_norm: float
    width_norm: float
    height_norm: float
    description: str
    confidence: float
    persistent: bool = False

@dataclass
class DetectorResult:
    detector_name: str
    status: Status
    score: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    anomalies: List[Anomaly] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    error_msg: Optional[str] = None

@dataclass
class QualityReport:
    file_path: str
    filename: str
    width: int
    height: int
    format: str
    overall_status: Status
    overall_confidence: float
    technical_quality: Dict[str, DetectorResult]
    processing_time_seconds: float
    error_msg: Optional[str] = None
