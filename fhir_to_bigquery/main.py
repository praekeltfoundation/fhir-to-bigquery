from datetime import datetime

from google.cloud import bigquery

from fhir_to_bigquery.high_water_mark import fetch_high_water_mark


def fetch_configured_high_water_mark(dataset_id: str) -> datetime | None:
    client = bigquery.Client()
    return fetch_high_water_mark(client, dataset_id)


def main() -> None:
    print("Hello from fhir-to-bigquery!")


if __name__ == "__main__":
    main()
