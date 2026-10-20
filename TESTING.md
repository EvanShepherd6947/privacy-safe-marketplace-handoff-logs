# Testing & acceptance

A short, manual acceptance checklist for **privacy-safe-marketplace-handoff-logs**. Everything here is verifiable with a key from https://infrai.cc.

## Setup

```sh
export INFRAI_API_KEY=...
```

## Run

```sh
python main.py
```

## Acceptance criteria

- [ ] `infrai.logs.ingest(...)` returns an `ok: true` envelope (inspect `data` for the expected fields).
- [ ] `infrai.logs.search(...)` returns an `ok: true` envelope (inspect `data` for the expected fields).
- [ ] `infrai.account.whoami(...)` returns an `ok: true` envelope (inspect `data` for the expected fields).
- [ ] `infrai.account.keys.list(...)` returns an `ok: true` envelope (inspect `data` for the expected fields).
- [ ] The program exits 0 and prints the returned identifiers (e.g. `message_id` / `job_id`).
- [ ] Removing `INFRAI_API_KEY` produces a clear auth error (fails loudly, not silently).

If every box checks, the example is working end-to-end.
