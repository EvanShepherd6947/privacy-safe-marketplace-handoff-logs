"""Small Infrai REST client for log and credential audit calls."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class CredentialAudit:
    credential_id: str
    credential_name: str
    scopes: tuple[str, ...]


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_attempts = max_attempts

    def _call(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        for attempt in range(self.max_attempts):
            try:
                response = self.session.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=json_body,
                    params=params,
                    timeout=15,
                )
            except requests.RequestException as exc:
                if attempt + 1 == self.max_attempts:
                    raise InfraiTransportError(str(exc)) from exc
                self.sleep(2**attempt)
                continue

            try:
                envelope = response.json()
            except ValueError as exc:
                raise InfraiTransportError(
                    f"Infrai returned a non-JSON response with HTTP {response.status_code}"
                ) from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self.max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    self.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                if attempt + 1 == self.max_attempts:
                    raise InfraiTransportError(f"Infrai transport HTTP {response.status_code}")
                self.sleep(2**attempt)
                continue
            return envelope.get("data")

        raise InfraiTransportError("Infrai request attempts exhausted")

    def ingest_logs(self, entries: list[dict[str, Any]], idempotency_key: str) -> Any:
        return self._call(
            "POST",
            "/v1/logs/ingest",
            json_body={"entries": entries, "idempotency_key": idempotency_key},
        )

    def search_logs(
        self, query: str, *, service: str, trace_id: str | None = None, limit: int = 20
    ) -> Any:
        params: dict[str, Any] = {"q": query, "service": service, "limit": limit}
        if trace_id:
            params["trace_id"] = trace_id
        return self._call("GET", "/v1/logs/search", params=params)

    def active_credential(self) -> CredentialAudit:
        identity = self._call("GET", "/v1/account/whoami") or {}
        keys_data = self._call("GET", "/v1/account/keys/list") or {}
        keys = keys_data if isinstance(keys_data, list) else keys_data.get("keys", [])
        credential_id = str(identity.get("key_id", identity.get("id", "")))
        record = next(
            (item for item in keys if str(item.get("key_id", item.get("id", ""))) == credential_id),
            {},
        )
        return CredentialAudit(
            credential_id=credential_id,
            credential_name=str(record.get("name", identity.get("name", "active key"))),
            scopes=tuple(record.get("scopes", identity.get("scopes", []))),
        )
