"""Run one representative marketplace handoff and search its audit trail."""

from dataclasses import asdict
import json
import sys

from infrai_client import InfraiClient
from marketplace_handoff import BuyerUpdate, HandoffRequest, SellerAsset, audit_handoff, record_handoff


def main() -> None:
    job_id = sys.argv[1] if len(sys.argv) > 1 else "handoff-demo-001"
    request = HandoffRequest(
        job_id=job_id,
        order_id="order-4721",
        seller_id="seller-88",
        required_update_sequence=3,
        assets=(SellerAsset("asset-front", "clean"), SellerAsset("asset-back", "clean")),
        buyer_update=BuyerUpdate("order-4721", 3),
    )
    client = InfraiClient()
    decision = record_handoff(client, request)
    audit = audit_handoff(client, job_id)
    output = {"decision": asdict(decision), "audit": audit}
    print(json.dumps(output, default=lambda value: asdict(value), indent=2))


if __name__ == "__main__":
    main()
