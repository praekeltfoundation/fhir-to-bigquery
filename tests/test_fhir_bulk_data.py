from fhir_to_bigquery.fhir_bulk_data import FhirBulkDataClient


class FakeResponse:
    def __init__(self, status_code, *, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.payload = payload or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.posts = []
        self.gets = []
        self.closed = False
        self.responses = [
            FakeResponse(200, payload={"access_token": "test-access-token"}),
            FakeResponse(202, headers={"Content-Location": "https://bulk/status/123"}),
        ]

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self.responses.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.closed = True


def test_medplum_client_starts_bulk_data_export_with_since(monkeypatch):
    session = FakeSession()
    session.responses = [
        FakeResponse(200, payload={"access_token": "test-access-token"}),
        FakeResponse(202, headers={"Content-Location": "https://bulk/status/123"}),
        FakeResponse(204),
    ]
    monkeypatch.setattr(
        "fhir_to_bigquery.fhir_bulk_data.httpx2.Client", lambda: session
    )
    client = FhirBulkDataClient(
        "https://api.medplum.com/fhir/R4",
        client_id="client-id",
        client_secret="client-secret",
    )

    manifest = client.export(since="2026-01-02T03:04:05Z")

    assert manifest is None
    assert session.posts == [
        (
            "https://api.medplum.com/oauth2/token",
            {
                "data": {
                    "grant_type": "client_credentials",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                }
            },
        ),
        (
            "https://api.medplum.com/fhir/R4/$export",
            {
                "headers": {"Prefer": "respond-async"},
                "params": {"_since": "2026-01-02T03:04:05Z"},
            },
        ),
    ]
    assert session.headers == {"Authorization": "Bearer test-access-token"}
    assert session.gets == [("https://bulk/status/123", {})]


def test_medplum_client_closes_http_client_after_export(monkeypatch):
    session = FakeSession()
    session.responses = [
        FakeResponse(200, payload={"access_token": "test-access-token"}),
        FakeResponse(202, headers={"Content-Location": "https://bulk/status/123"}),
        FakeResponse(204),
    ]
    monkeypatch.setattr(
        "fhir_to_bigquery.fhir_bulk_data.httpx2.Client", lambda: session
    )

    client = FhirBulkDataClient(
        "https://api.medplum.com/fhir/R4",
        client_id="client-id",
        client_secret="client-secret",
    )
    client.export()

    assert session.closed is True


def test_medplum_client_exports_bulk_data_manifest(monkeypatch):
    session = FakeSession()
    session.responses = [
        FakeResponse(200, payload={"access_token": "test-access-token"}),
        FakeResponse(202, headers={"Content-Location": "https://bulk/status/123"}),
        FakeResponse(202, headers={"Retry-After": "3"}),
        FakeResponse(
            200,
            payload={
                "transactionTime": "2026-01-02T03:04:05Z",
                "request": "https://api.medplum.com/fhir/R4/$export",
                "requiresAccessToken": True,
                "output": [
                    {
                        "type": "Patient",
                        "url": "https://storage.example/patient.ndjson",
                    }
                ],
            },
        ),
    ]
    sleeps = []
    monkeypatch.setattr(
        "fhir_to_bigquery.fhir_bulk_data.httpx2.Client", lambda: session
    )
    monkeypatch.setattr("fhir_to_bigquery.fhir_bulk_data.time.sleep", sleeps.append)
    client = FhirBulkDataClient(
        "https://api.medplum.com/fhir/R4",
        client_id="client-id",
        client_secret="client-secret",
    )

    manifest = client.export(since="2026-01-02T03:04:05Z")

    assert manifest == {
        "transactionTime": "2026-01-02T03:04:05Z",
        "request": "https://api.medplum.com/fhir/R4/$export",
        "requiresAccessToken": True,
        "output": [
            {
                "type": "Patient",
                "url": "https://storage.example/patient.ndjson",
            }
        ],
    }
    assert sleeps == [3]
    assert session.posts == [
        (
            "https://api.medplum.com/oauth2/token",
            {
                "data": {
                    "grant_type": "client_credentials",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                }
            },
        ),
        (
            "https://api.medplum.com/fhir/R4/$export",
            {
                "headers": {"Prefer": "respond-async"},
                "params": {"_since": "2026-01-02T03:04:05Z"},
            },
        ),
    ]
    assert session.gets == [
        ("https://bulk/status/123", {}),
        ("https://bulk/status/123", {}),
    ]
    assert session.headers == {"Authorization": "Bearer test-access-token"}


def test_medplum_client_uses_default_poll_delay_without_retry_after(monkeypatch):
    session = FakeSession()
    session.responses = [
        FakeResponse(200, payload={"access_token": "test-access-token"}),
        FakeResponse(202, headers={"Content-Location": "https://bulk/status/123"}),
        FakeResponse(202),
        FakeResponse(
            200,
            payload={
                "output": [
                    {
                        "type": "Patient",
                        "url": "https://storage.example/patient.ndjson",
                    }
                ]
            },
        ),
    ]
    sleeps = []
    monkeypatch.setattr(
        "fhir_to_bigquery.fhir_bulk_data.httpx2.Client", lambda: session
    )
    monkeypatch.setattr("fhir_to_bigquery.fhir_bulk_data.time.sleep", sleeps.append)
    client = FhirBulkDataClient(
        "https://api.medplum.com/fhir/R4",
        client_id="client-id",
        client_secret="client-secret",
        default_retry_after_seconds=60,
    )

    client.export()

    assert sleeps == [60]


def test_medplum_client_returns_none_for_empty_bulk_data_export(monkeypatch):
    no_content_session = FakeSession()
    no_content_session.responses = [
        FakeResponse(200, payload={"access_token": "test-access-token"}),
        FakeResponse(202, headers={"Content-Location": "https://bulk/status/123"}),
        FakeResponse(204),
    ]
    empty_output_session = FakeSession()
    empty_output_session.responses = [
        FakeResponse(200, payload={"access_token": "test-access-token"}),
        FakeResponse(202, headers={"Content-Location": "https://bulk/status/456"}),
        FakeResponse(200, payload={"output": []}),
    ]
    sessions = [no_content_session, empty_output_session]
    monkeypatch.setattr(
        "fhir_to_bigquery.fhir_bulk_data.httpx2.Client", lambda: sessions.pop(0)
    )
    no_content_client = FhirBulkDataClient(
        "https://api.medplum.com/fhir/R4",
        client_id="client-id",
        client_secret="client-secret",
    )
    empty_output_client = FhirBulkDataClient(
        "https://api.medplum.com/fhir/R4",
        client_id="client-id",
        client_secret="client-secret",
    )

    no_content_manifest = no_content_client.export()
    empty_output_manifest = empty_output_client.export()

    assert no_content_manifest is None
    assert empty_output_manifest is None
