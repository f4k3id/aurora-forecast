from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Optional
import json

ZoneName = Literal["polar", "auroral", "subauroral"]
Level = Literal["quiet", "unsettled", "active", "stormy"]

@dataclass
class ZoneForecast:
    zone: ZoneName
    last_24h: Optional[str] = None
    last_6h: Optional[str] = None
    next_6h: Optional[str] = None
    next_24h: Optional[str] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class RNCanSnapshot:
    issued_at: str                 # e.g. "2026-06-08 14:32 UT"
    timestamp: str                 # ISO when we fetched
    zones: dict[ZoneName, ZoneForecast]
    raw_text: str = ""
    images: dict[str, str] = None  # optional RNCan map/chart URLs

    def to_dict(self):
        d = {
            "issued_at": self.issued_at,
            "timestamp": self.timestamp,
            "zones": {k: v.to_dict() for k, v in self.zones.items()},
            "raw_text": self.raw_text,
        }
        if self.images:
            d["images"] = self.images
        return d

@dataclass
class KpPoint:
    time_tag: str   # ISO
    kp: float
    a_running: Optional[int] = None
    station_count: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class CurrentState:
    rncan: Optional[RNCanSnapshot] = None
    latest_kp: Optional[KpPoint] = None
    kp_history: list[KpPoint] = field(default_factory=list)
    activity_history: list[dict] = field(default_factory=list)  # [{"t": iso, "score": 0-3, "label": str}]
    last_fetch: Optional[str] = None   # ISO
    last_stormy_zones: set[str] = field(default_factory=set)  # for notification dedup

    def to_dict(self):
        d = {
            "rncan": self.rncan.to_dict() if self.rncan else None,
            "latest_kp": self.latest_kp.to_dict() if self.latest_kp else None,
            "kp_history": [p.to_dict() for p in self.kp_history],
            "activity_history": self.activity_history,
            "last_fetch": self.last_fetch,
            "last_stormy_zones": list(self.last_stormy_zones),
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "CurrentState":
        if not data:
            return cls()
        rncan = None
        if data.get("rncan"):
            z = {}
            for zn, zd in data["rncan"]["zones"].items():
                z[zn] = ZoneForecast(**zd)
            rncan = RNCanSnapshot(
                issued_at=data["rncan"]["issued_at"],
                timestamp=data["rncan"]["timestamp"],
                zones=z,
                raw_text=data["rncan"].get("raw_text", ""),
                images=data["rncan"].get("images"),
            )
        latest_kp = KpPoint(**data["latest_kp"]) if data.get("latest_kp") else None
        kp_hist = [KpPoint(**p) for p in data.get("kp_history", [])]
        act_hist = data.get("activity_history", [])
        return cls(
            rncan=rncan,
            latest_kp=latest_kp,
            kp_history=kp_hist,
            activity_history=act_hist,
            last_fetch=data.get("last_fetch"),
            last_stormy_zones=set(data.get("last_stormy_zones", [])),
        )
