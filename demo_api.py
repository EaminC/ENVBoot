from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


app = FastAPI(title="ENVBoot Mock Resource API", version="0.1.0")


# ===== In-memory state =====
capacities: Dict[str, int] = {
    "current": 1,
    "zone-b": 1,
    "zone-c": 0,
}

leases: List[Dict] = [
    # Block the whole day in current to demonstrate time-shift or zone change
    {
        "id": "lease-now-current",
        "status": "ACTIVE",
        "start": "2025-09-02T00:00:00Z",
        "end": "2025-09-02T23:59:00Z",
        "zone": "current",
        "min": 1,
    },
    # Old lease in zone-b to keep it free now
    {
        "id": "lease-old-zone-b",
        "status": "DELETED",
        "start": "2025-08-01T00:00:00Z",
        "end": "2025-08-01T01:00:00Z",
        "zone": "zone-b",
        "min": 1,
    },
]


# ===== Models =====
class AvailabilityResponse(BaseModel):
    requested: Dict
    decision: str
    selection: Optional[Dict] = None
    explanation: Optional[str] = None
    no_available_window: Optional[bool] = None
    checked_steps: Optional[int] = None
    checked_zones: Optional[List[str]] = None


class ReserveRequest(BaseModel):
    zone: str
    start: str
    end: str


class ReserveResponse(BaseModel):
    lease_id: str
    zone: str
    start: str
    end: str


# ===== Helpers =====
def parse_iso(s: str) -> datetime:
    # Accept both ...Z and with offset
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start


def occupancy(zone: str, start: datetime, end: datetime) -> int:
    occ = 0
    for l in leases:
        if l.get("status") not in ("ACTIVE", "STARTED"):
            continue
        if l.get("zone") != zone:
            continue
        try:
            ls = parse_iso(l["start"])  # type: ignore[index]
            le = parse_iso(l["end"])    # type: ignore[index]
        except Exception:
            continue
        if overlaps(start, end, ls, le):
            occ += int(l.get("min", 1) or 1)
    return occ


def capacity(zone: str, threshold_override: Optional[int] = None, primary: bool = False) -> int:
    if primary and threshold_override is not None:
        return int(threshold_override)
    return int(capacities.get(zone, 1))


def available(zone: str, start: datetime, end: datetime, need: int = 1,
              threshold_override: Optional[int] = None, primary: bool = False) -> bool:
    occ = occupancy(zone, start, end)
    cap = capacity(zone, threshold_override, primary)
    return (occ + need) <= cap


def find_window(primary_zone: str,
                alt_zones: List[str],
                start: datetime,
                duration_hours: float,
                step_minutes: int,
                lookahead_hours: int,
                threshold: Optional[int]) -> Optional[Dict]:
    zones_to_check = [primary_zone] + [z for z in alt_zones if z and z != primary_zone]
    need = 1
    duration = timedelta(hours=duration_hours)
    start_time = start
    end_time = start_time + duration

    # Try requested time across zones (primary with threshold override)
    for i, z in enumerate(zones_to_check):
        is_primary = (i == 0)
        if available(z, start_time, end_time, need, threshold_override=threshold, primary=is_primary):
            return {
                "zone": z,
                "start": start_time,
                "end": end_time,
                "shift_minutes": 0,
            }

    # Scan forward
    step = timedelta(minutes=step_minutes)
    cursor = start_time + step
    deadline = start_time + timedelta(hours=lookahead_hours)
    while cursor <= deadline:
        test_start = cursor
        test_end = test_start + duration
        for i, z in enumerate(zones_to_check):
            is_primary = (i == 0)
            if available(z, test_start, test_end, need, threshold_override=threshold, primary=is_primary):
                return {
                    "zone": z,
                    "start": test_start,
                    "end": test_end,
                    "shift_minutes": int((test_start - start_time).total_seconds() // 60),
                }
        cursor += step
    return None


# ===== Routes =====
@app.get("/", tags=["meta"])
def root():
    return {"status": "ok", "capacities": capacities, "active_leases": len([l for l in leases if l.get("status") == "ACTIVE"]) }


@app.get("/availability", response_model=AvailabilityResponse, tags=["availability"]) 
def get_availability(
    region: str = Query(..., description="Primary zone, e.g., 'current'"),
    req_vcpus: int = Query(2),
    req_ram_gb: int = Query(4),
    req_gpus: int = Query(0),
    start: str = Query(..., description="Requested start ISO, e.g., 2025-09-02T00:00:00Z"),
    duration_hours: float = Query(4.0),
    threshold: int = Query(1, description="Capacity threshold for the requested region"),
    alt_zones: str = Query("", description="Comma-separated alt zones"),
    step_minutes: int = Query(30),
    lookahead_hours: int = Query(48),
):
    try:
        start_dt = parse_iso(start)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start datetime")

    alt_list = [z.strip() for z in alt_zones.split(",") if z.strip()] if alt_zones else []
    sel = find_window(
        primary_zone=region,
        alt_zones=alt_list,
        start=start_dt,
        duration_hours=duration_hours,
        step_minutes=step_minutes,
        lookahead_hours=lookahead_hours,
        threshold=threshold,
    )

    requested = {
        "region": region,
        "req_vcpus": req_vcpus,
        "req_ram_gb": req_ram_gb,
        "req_gpus": req_gpus,
        "start": start,
        "duration_hours": duration_hours,
        "threshold": threshold,
        "alt_zones": alt_list,
        "step_minutes": step_minutes,
        "lookahead_hours": lookahead_hours,
    }

    if sel is None:
        return AvailabilityResponse(
            requested=requested,
            decision="none",
            no_available_window=True,
            checked_steps=int((lookahead_hours * 60) // step_minutes),
            checked_zones=[region] + alt_list,
        )

    zone = sel["zone"]
    sel_start = sel["start"]
    sel_end = sel["end"]
    shift = sel.get("shift_minutes", 0)
    if shift == 0 and zone == region:
        decision = "now"
        explanation = f"Requested slot available in {region}."
    elif shift == 0 and zone != region:
        decision = "zone_change"
        explanation = f"Requested slot unavailable in {region}; available in {zone}."
    elif shift > 0 and zone == region:
        decision = "time_shift"
        explanation = f"First available in {region} after {shift} minutes."
    else:
        decision = "zone_change"
        explanation = f"First available in {zone} after {shift} minutes."

    return AvailabilityResponse(
        requested=requested,
        decision=decision,
        selection={
            "zone": zone,
            "start": to_iso(sel_start),
            "end": to_iso(sel_end),
        },
        explanation=explanation,
    )


@app.post("/reserve", response_model=ReserveResponse, status_code=201, tags=["reserve"]) 
def post_reserve(body: ReserveRequest):
    try:
        start_dt = parse_iso(body.start)
        end_dt = parse_iso(body.end)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid datetime in request body")

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="end must be after start")

    # Check availability under configured capacities (no threshold override here)
    occ = occupancy(body.zone, start_dt, end_dt)
    cap = capacity(body.zone)
    if (occ + 1) > cap:
        raise HTTPException(status_code=409, detail={
            "message": "Capacity exceeded for requested window",
            "zone": body.zone,
            "occupancy": occ,
            "capacity": cap,
        })

    # Create the lease
    lease_id = str(uuid4())
    new_lease = {
        "id": lease_id,
        "status": "ACTIVE",
        "start": to_iso(start_dt),
        "end": to_iso(end_dt),
        "zone": body.zone,
        "min": 1,
    }
    leases.append(new_lease)

    return ReserveResponse(
        lease_id=lease_id,
        zone=body.zone,
        start=new_lease["start"],
        end=new_lease["end"],
    )


# Also expose an alias to match README example if needed
app_ = app
