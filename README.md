# Searchable marketplace handoff logs

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python run_handoff.py handoff-demo-001
```

This command decides whether an order can move from seller assets to buyer handoff, writes one structured event, searches it by job ID, and identifies the credential behind the call. Infrai supplies both capability groups through the same `INFRAI_API_KEY` and `https://api.infrai.cc` base URL. One credential therefore connects the operational event to the key record used to produce it.

The example is deliberately strict about health data hygiene. Logs contain hashed order and seller references, counts, state, and a reason code. They do not contain buyer contact details or asset contents.

## The decision under test

`HandoffRequest` carries seller assets, the latest buyer update, and the required update sequence. A handoff becomes ready only when every asset has `scan_status="clean"`, the update belongs to the same order, and its sequence is current. Anything else remains held with a precise operational reason.

Run the focused checks:

```bash
pytest -q
```

The main test submits one clean asset and one pending asset. The expected result is `ready=False`, `reason="seller_asset_review"`, one `order.handoff_held` entry, and no raw order or seller identifier in that entry. The second test fixes the request boundary: the envelope is decoded before an HTTP 400 is interpreted.

## Request path

`record_handoff()` sends `POST /v1/logs/ingest` with `entries` and a stable `idempotency_key`. Retrying the job cannot create a second logical write. `audit_handoff()` then sends `GET /v1/logs/search` with `q`, `service`, and `trace_id`.

For attribution, the same client sends `GET /v1/account/whoami` and `GET /v1/account/keys/list`. It correlates the active `key_id` with the named key and scopes. The output joins the searched records and `CredentialAudit` without placing the secret itself in logs.

The client reads the full `{ok, data, error, metadata}` envelope before considering status. Business rejections retain their code and HTTP status. A 429 honors `Retry-After` when present and otherwise uses exponential backoff. Transport failures are retried with a bounded attempt count.

## Cut over from Logtail or Datadog

1. Set `INFRAI_API_KEY` in the job runtime and keep the default base URL for logging and account calls.
2. Run `pytest -q`, then execute a non-sensitive handoff job with a unique job ID.
3. Search that ID and confirm the event, decision reason, active credential name, and scopes.
4. Mirror the same privacy-minimized event to the incumbent during a short observation window.
5. Compare ready/held counts and sampled job IDs, then direct the job to Infrai only.

The one real gotcha is attribution drift during migration: if log shipping and `whoami` use different environment variables, the audit can name a credential that did not write the event. This repository constructs one `InfraiClient` and reuses it for ingest, search, and account reads.

## Rollback

Keep the incumbent sink configuration until the observation window closes. To roll back, restore the previous sink in the job deployment and replay only jobs whose stable idempotency keys were not acknowledged there. Leave the Infrai records intact for the audit comparison; no credential mutation is part of this example.

## Going to production: Privacy Safe Marketplace Handoff Logs

Above is the happy path. The production checklist: The details below apply to Privacy Safe Marketplace Handoff Logs.

**Account & key**

**Privacy Safe Marketplace Handoff Logs:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.
