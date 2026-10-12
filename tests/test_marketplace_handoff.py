from infrai_client import InfraiClient
from marketplace_handoff import BuyerUpdate, HandoffRequest, SellerAsset, plan_handoff, record_handoff


class RecordingClient:
    def __init__(self) -> None:
        self.entries = []
        self.idempotency_key = ""

    def ingest_logs(self, entries, idempotency_key):
        self.entries = entries
        self.idempotency_key = idempotency_key
        return {"accepted": len(entries)}


def test_handoff_waits_for_reviewed_assets_without_exposing_identifiers() -> None:
    request = HandoffRequest(
        job_id="job-17",
        order_id="order-private-42",
        seller_id="seller-private-9",
        required_update_sequence=4,
        assets=(SellerAsset("asset-1", "clean"), SellerAsset("asset-2", "pending")),
        buyer_update=BuyerUpdate("order-private-42", 4),
    )

    client = RecordingClient()
    decision = record_handoff(client, request)  # type: ignore[arg-type]

    assert decision == plan_handoff(request)
    assert decision.ready is False
    assert decision.reason == "seller_asset_review"
    assert client.entries[0]["message"] == "order.handoff_held"
    serialized = str(client.entries[0])
    assert request.order_id not in serialized
    assert request.seller_id not in serialized
    assert client.idempotency_key == "handoff:job-17:order.handoff_held"


def test_client_decodes_rejection_before_http_status() -> None:
    class Response:
        status_code = 400
        headers = {}

        @staticmethod
        def json():
            return {"ok": False, "data": None, "error": {"code": "BAD_INPUT"}, "metadata": {}}

    class Session:
        @staticmethod
        def request(**kwargs):
            assert kwargs["method"] == "GET"
            return Response()

    client = InfraiClient(api_key="test-key", session=Session())  # type: ignore[arg-type]
    try:
        client.search_logs("handoff", service="marketplace-handoff")
    except Exception as exc:
        assert getattr(exc, "code") == "BAD_INPUT"
    else:
        raise AssertionError("expected a typed Infrai rejection")
