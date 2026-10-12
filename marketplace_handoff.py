"""Privacy-minimized marketplace handoff decisions and structured log records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal

from infrai_client import InfraiClient

SERVICE = "marketplace-handoff"


@dataclass(frozen=True)
class SellerAsset:
    asset_id: str
    scan_status: Literal["clean", "pending", "blocked"]


@dataclass(frozen=True)
class BuyerUpdate:
    order_id: str
    sequence: int


@dataclass(frozen=True)
class HandoffRequest:
    job_id: str
    order_id: str
    seller_id: str
    required_update_sequence: int
    assets: tuple[SellerAsset, ...]
    buyer_update: BuyerUpdate


@dataclass(frozen=True)
class HandoffDecision:
    ready: bool
    event: str
    reason: str


def plan_handoff(request: HandoffRequest) -> HandoffDecision:
    assets_clean = bool(request.assets) and all(
        asset.scan_status == "clean" for asset in request.assets
    )
    buyer_current = (
        request.buyer_update.order_id == request.order_id
        and request.buyer_update.sequence >= request.required_update_sequence
    )
    if assets_clean and buyer_current:
        return HandoffDecision(True, "order.handoff_ready", "assets_clean_and_buyer_current")
    if not assets_clean:
        return HandoffDecision(False, "order.handoff_held", "seller_asset_review")
    return HandoffDecision(False, "order.handoff_held", "buyer_update_pending")


def _reference(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def record_handoff(client: InfraiClient, request: HandoffRequest) -> HandoffDecision:
    decision = plan_handoff(request)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "info" if decision.ready else "warning",
        "service": SERVICE,
        "environment": "production",
        "trace_id": request.job_id,
        "message": decision.event,
        "metadata": {
            "order_ref": _reference(request.order_id),
            "seller_ref": _reference(request.seller_id),
            "asset_count": len(request.assets),
            "buyer_update_sequence": request.buyer_update.sequence,
            "decision_reason": decision.reason,
        },
    }
    client.ingest_logs([entry], idempotency_key=f"handoff:{request.job_id}:{decision.event}")
    return decision


def audit_handoff(client: InfraiClient, job_id: str) -> dict[str, object]:
    return {
        "logs": client.search_logs("order.handoff", service=SERVICE, trace_id=job_id),
        "credential": client.active_credential(),
    }
