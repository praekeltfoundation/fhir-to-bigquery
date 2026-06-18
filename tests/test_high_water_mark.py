from datetime import UTC, datetime

from fhir_to_bigquery.high_water_mark import fetch_high_water_mark


class FakeSchemaField:
    def __init__(self, name, fields=()):
        self.name = name
        self.fields = fields


class FakeTable:
    def __init__(self, table_id, schema, table_type="TABLE"):
        self.table_id = table_id
        self.schema = schema
        self.table_type = table_type


class FakeQueryJob:
    def __init__(self, high_water_marks):
        self.high_water_marks = high_water_marks

    def result(self):
        return [{"high_water_mark": max(self.high_water_marks)}]


class FakeSingleQueryJob:
    def __init__(self, high_water_mark):
        self.high_water_mark = high_water_mark

    def result(self):
        return [{"high_water_mark": self.high_water_mark}]


class FakeBigQueryClient:
    def __init__(self, query_results=None):
        self.tables = [
            FakeTable(
                "patient",
                [FakeSchemaField("meta", [FakeSchemaField("lastUpdated")])],
            )
        ]
        self.query_results = query_results or {
            "patient": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        }
        self.queries = []

    def list_tables(self, dataset):
        return self.tables

    def get_table(self, table):
        table_id = table.rsplit(".", maxsplit=1)[1]
        return next(table for table in self.tables if table.table_id == table_id)

    def query(self, query):
        self.queries.append(query)
        high_water_marks = [
            high_water_mark
            for table_id, high_water_mark in self.query_results.items()
            if f".{table_id}`" in query and high_water_mark is not None
        ]
        if high_water_marks:
            return FakeQueryJob(high_water_marks)

        return FakeSingleQueryJob(None)


def test_fetches_high_water_mark_from_active_fhir_resource_table():
    client = FakeBigQueryClient()

    high_water_mark = fetch_high_water_mark(client, "project.dataset")

    assert high_water_mark == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert client.queries == [
        "SELECT MAX(high_water_mark) AS high_water_mark FROM ("
        "SELECT MAX(meta.lastUpdated) AS high_water_mark FROM `project.dataset.patient`"
        ")"
    ]


def test_fetches_latest_high_water_mark_across_active_fhir_resource_tables():
    client = FakeBigQueryClient(
        {
            "patient": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            "observation": datetime(2026, 1, 3, 3, 4, 5, tzinfo=UTC),
        }
    )
    client.tables = [
        FakeTable(
            "patient",
            [FakeSchemaField("meta", [FakeSchemaField("lastUpdated")])],
        ),
        FakeTable(
            "observation",
            [FakeSchemaField("meta", [FakeSchemaField("lastUpdated")])],
        ),
    ]

    high_water_mark = fetch_high_water_mark(client, "project.dataset")

    assert high_water_mark == datetime(2026, 1, 3, 3, 4, 5, tzinfo=UTC)
    assert client.queries == [
        "SELECT MAX(high_water_mark) AS high_water_mark FROM ("
        "SELECT MAX(meta.lastUpdated) AS high_water_mark FROM `project.dataset.patient` "
        "UNION ALL "
        "SELECT MAX(meta.lastUpdated) AS high_water_mark FROM `project.dataset.observation`"
        ")"
    ]


def test_ignores_non_active_tables_when_fetching_high_water_mark():
    client = FakeBigQueryClient(
        {
            "patient": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            "analytics_view": datetime(2026, 1, 4, 3, 4, 5, tzinfo=UTC),
            "audit": datetime(2026, 1, 5, 3, 4, 5, tzinfo=UTC),
        }
    )
    client.tables = [
        FakeTable(
            "patient",
            [FakeSchemaField("meta", [FakeSchemaField("lastUpdated")])],
        ),
        FakeTable(
            "analytics_view",
            [FakeSchemaField("meta", [FakeSchemaField("lastUpdated")])],
            table_type="VIEW",
        ),
        FakeTable("audit", [FakeSchemaField("created_at")]),
    ]

    high_water_mark = fetch_high_water_mark(client, "project.dataset")

    assert high_water_mark == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert client.queries == [
        "SELECT MAX(high_water_mark) AS high_water_mark FROM ("
        "SELECT MAX(meta.lastUpdated) AS high_water_mark FROM `project.dataset.patient`"
        ")"
    ]


def test_returns_none_when_no_high_water_mark_exists():
    client = FakeBigQueryClient({"patient": None})

    high_water_mark = fetch_high_water_mark(client, "project.dataset")

    assert high_water_mark is None


def test_returns_none_when_active_tables_have_no_high_water_marks():
    client = FakeBigQueryClient({"patient": None, "observation": None})
    client.tables = [
        FakeTable(
            "patient",
            [FakeSchemaField("meta", [FakeSchemaField("lastUpdated")])],
        ),
        FakeTable(
            "observation",
            [FakeSchemaField("meta", [FakeSchemaField("lastUpdated")])],
        ),
    ]

    high_water_mark = fetch_high_water_mark(client, "project.dataset")

    assert high_water_mark is None
    assert client.queries == [
        "SELECT MAX(high_water_mark) AS high_water_mark FROM ("
        "SELECT MAX(meta.lastUpdated) AS high_water_mark FROM `project.dataset.patient` "
        "UNION ALL "
        "SELECT MAX(meta.lastUpdated) AS high_water_mark FROM `project.dataset.observation`"
        ")"
    ]
