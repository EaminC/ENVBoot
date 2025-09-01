from dataclasses import dataclass
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ComplexityTier(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    HEAVY = "heavy"
    VERY_HEAVY = "very_heavy"

@dataclass
class ResourceRequest:
    vcpus: int
    ram_gb: int
    gpus: int
    disk_gb: int = 20
    bare_metal: bool = False

@dataclass
class DowngradePolicy:
    allow_gpu_to_cpu: bool = True
    max_vcpu_reduction_ratio: float = 0.5
    max_ram_reduction_ratio: float = 0.25
    max_duration_increase_ratio: float = 2.0
    require_pass_smoketest: bool = True

@dataclass
class SchedulingConfig:
    lookahead_hours: int = 72
    step_minutes: int = 60
    preferred_zone: str = "current"
    alt_zones: List[str] = None
    start_by: Optional[datetime] = None

@dataclass
class ReservationPlan:
    zone: str
    start: datetime
    end: datetime
    flavor: str
    count: int
    reservation_id: Optional[str] = None
    lease_id: Optional[str] = None

@dataclass
class CaseStudyResult:
    case: str
    inputs: Dict[str, Any]
    decisions: List[Dict[str, Any]]
    reservation: ReservationPlan
    su_estimate_per_hour: float
    su_estimate_total: float
    slo: Dict[str, Any]
    smoke_test: Optional[Dict[str, Any]] = None
    complexity_tier: Optional[ComplexityTier] = None
