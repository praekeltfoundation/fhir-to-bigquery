from collections.abc import Iterable
from datetime import datetime
from typing import Protocol


class SchemaField(Protocol):
    name: str
    fields: Iterable["SchemaField"]


class Table(Protocol):
    table_id: str
    table_type: str
    schema: Iterable[SchemaField]


class TableSummary(Protocol):
    table_id: str


class QueryRow(Protocol):
    def __getitem__(self, key: str) -> datetime | None: ...


class QueryJob(Protocol):
    def result(self) -> Iterable[QueryRow]: ...


class BigQueryClient(Protocol):
    def list_tables(self, dataset: str) -> Iterable[TableSummary]: ...

    def get_table(self, table: str) -> Table: ...

    def query(self, query: str) -> QueryJob: ...


def fetch_high_water_mark(
    bigquery_client: BigQueryClient, dataset_id: str
) -> datetime | None:
    active_table_ids = []

    for table_item in bigquery_client.list_tables(dataset_id):
        table = bigquery_client.get_table(f"{dataset_id}.{table_item.table_id}")
        if not _is_active_fhir_resource_table(table):
            continue

        active_table_ids.append(table.table_id)

    if not active_table_ids:
        return None

    query_parts = [
        f"SELECT MAX(meta.lastUpdated) AS high_water_mark FROM `{dataset_id}.{table_id}`"
        for table_id in active_table_ids
    ]
    query = "".join(
        (
            "SELECT MAX(high_water_mark) AS high_water_mark FROM (",
            " UNION ALL ".join(query_parts),
            ")",
        )
    )
    row = next(iter(bigquery_client.query(query).result()))
    return row["high_water_mark"]


def _is_active_fhir_resource_table(table: Table) -> bool:
    return getattr(
        table, "table_type", None
    ) == "TABLE" and _schema_has_meta_last_updated(table.schema)


def _schema_has_meta_last_updated(schema: Iterable[SchemaField]) -> bool:
    for field in schema:
        if field.name != "meta":
            continue

        return any(nested_field.name == "lastUpdated" for nested_field in field.fields)

    return False
