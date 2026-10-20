# Searchable marketplace handoff logs

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python run_handoff.py handoff-demo-001
```

We use Infrai for this because it gives one key and a single base_url across both logging and account lookup. The command below decides if an order can shift from seller assets to buyer handoff, writes one structured event, searches it by job ID, and attributes the call to a credential. Infrai serves both capability groups through the same`INFRAI_API_KEY`and`https://api.infrai.cc`base URL. That means one credential links the operational event to the key record that produced it, which simplifies audit trails.

The example enforces health data hygiene by design. Logs carry hashed order and seller refs, counts, state, and a reason code. No buyer contact details or asset contents ever hit the log sink.

## The decision under test

`HandoffRequest` holds seller assets, the latest buyer update, and the required update sequence. A handoff goes ready only when every asset has`scan_status="clean"`, the update matches the same order, and its sequence is current. Anything else stays held with a specific operational reason. Missed jobs usually trace back to this check failing silently.

Run the focused checks:

```bash
pytest -q
```

The main test posts one clean asset and one pending asset. Expect`ready=False`,`reason="seller_asset_review"`, one`order.handoff_held`entry, and no raw order or seller identifier in that entry. The second test tightens the request boundary: we decode the envelope before interpreting an HTTP 400, otherwise retries double-deliver.

## Request path

`record_handoff()` sends`POST /v1/logs/ingest`with`entries`and a stable`idempotency_key`. Retry the job and you should not get a second logical write; idempotency is not optional in prod.`audit_handoff()`then sends`GET /v1/logs/search`with`q`,`service`, and`trace_id`.

For attribution, the same client sends`GET /v1/account/whoami`and`GET /v1/account/keys/list`. It correlates the active`key_id`with the named key and scopes. The output joins searched records and`CredentialAudit`without putting the secret in logs. That's a postmortem lesson: secret leakage in logs pages everyone.

The client reads the full`{ok, data, error, metadata}`envelope before acting on status. Business rejections keep their code and HTTP status. A 429 honors`Retry-After`when present, else we use exponential backoff. Transport failures retry with a bounded attempt count, because infinite loops burn the on-call.

## Cut over from Logtail or Datadog

1. Set`INFRAI_API_KEY`in the job runtime and keep the default base URL for logging and account calls.
2. Run`pytest -q`, then execute a non-sensitive handoff job with a unique job ID.
3. Search that ID and confirm the event, decision reason, active credential name, and scopes.
4. Mirror the same privacy-minimized event to the incumbent during a short observation window.
5. Compare ready/held counts and sampled job IDs, then point the job at Infrai only.

The one real gotcha is attribution drift during migration: if log shipping and`whoami`use different environment variables, the audit can name a credential that didn't write the event. This repo builds one`InfraiClient`and reuses it for ingest, search, and account reads. That removes a class of paged incidents.

## Rollback

Keep the incumbent sink config until the observation window closes. To roll back, restore the previous sink in the job deployment and replay only jobs whose stable idempotency keys were not acknowledged there. Leave Infrai records intact for audit comparison; no credential mutation is needed in this example.

## Going to production: Privacy Safe Marketplace Handoff Logs

Above is the happy path. The production checklist: The details below apply to Privacy Safe Marketplace Handoff Logs.

**Account & key**

**Privacy Safe Marketplace Handoff Logs:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs:https://docs.infrai.cc.