import time
from urllib.parse import urlparse

import httpx2


class FhirBulkDataClient:
    def __init__(
        self,
        base_url: str,
        *,
        client_id: str,
        client_secret: str,
        default_retry_after_seconds: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.default_retry_after_seconds = default_retry_after_seconds
        self._access_token: str | None = None

    def export(self, *, since: str | None = None) -> dict | None:
        with httpx2.Client() as session:
            status_url = self._start_export(session, since=since)
            return self._poll_export(session, status_url)

    def _start_export(self, session: httpx2.Client, *, since: str | None = None) -> str:
        self._authorize_session(session)
        params = {"_since": since} if since is not None else None
        response = session.post(
            f"{self.base_url}/$export",
            headers={"Prefer": "respond-async"},
            params=params,
        )
        response.raise_for_status()
        return response.headers["Content-Location"]

    def _poll_export(self, session: httpx2.Client, status_url: str) -> dict | None:
        self._authorize_session(session)
        while True:
            response = session.get(status_url)
            response.raise_for_status()
            if response.status_code == 204:
                return None

            if response.status_code == 200:
                manifest = response.json()
                if not manifest.get("output"):
                    return None

                return manifest

            retry_after = response.headers.get("Retry-After")
            time.sleep(
                int(retry_after)
                if retry_after is not None
                else self.default_retry_after_seconds
            )

    def _authorize_session(self, session: httpx2.Client) -> None:
        if self._access_token is None:
            self._access_token = self._fetch_access_token(session)

        session.headers.update({"Authorization": f"Bearer {self._access_token}"})

    def _fetch_access_token(self, session: httpx2.Client) -> str:
        response = session.post(
            self._token_url(),
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _token_url(self) -> str:
        parsed_url = urlparse(self.base_url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}/oauth2/token"
