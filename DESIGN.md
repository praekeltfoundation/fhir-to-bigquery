### System Specification: FHIR to BigQuery ETL Pipeline

Implement a stateless, memory-efficient Python ETL script packaged as a Kubernetes CronJob. The purpose of this tool is to incrementally or fully extract all clinical resource tables from a Medplum FHIR API using the standard FHIR Bulk Data Access (`$export`) protocol and stream them directly into Google Cloud BigQuery.

#### 1. Core Architecture & Execution Modes

The script must support a configuration parameter (e.g., via an environment variable `SYNC_MODE=INCREMENTAL` or `FULL`) to toggle between two execution strategies using the same codebase:

* **Incremental Sync Mode (`INCREMENTAL`):**
1. Query the target BigQuery dataset to find the global High-Water Mark: `SELECT MAX(meta.lastUpdated) FROM [dataset].[any_active_table]`. If multiple tables exist, find the absolute maximum across them.
2. If a timestamp is found, apply an **overlap buffer by subtracting a configurable amount of time** from it, defaulting to 10 minutes. Format this as an ISO 8601 timestamp string.
3. If no timestamp is found (empty dataset), gracefully fall back to **Full Sync Mode** behavior.
4. Initiate the export by sending a `POST` request to `[FHIR_BASE_URL]/$export?_since=[BUFFERED_TIMESTAMP]`.


* **Full Sync Mode (`FULL`):**
1. Do not query BigQuery for a timestamp.
2. Initiate the export by sending a `POST` request to `[FHIR_BASE_URL]/$export` without a `_since` parameter.



#### 2. Handshake, Polling, and Async Flow

* The initial `POST` request must include the HTTP header `Prefer: respond-async`.
* Capture the `Content-Location` URL from the `202 Accepted` response headers.
* Implement a synchronous `while` loop to poll the status URL.
* Inspect the `Retry-After` header during polling responses and make the script sleep for that duration before making the next request to prevent rate-limiting.
* Handle empty exports gracefully: If the status endpoint returns `204 No Content` or a `200 OK` with an empty `"output"` manifest array, log `"No new data found"`, commit no changes, and exit cleanly with code `0`.

#### 3. Streaming Ingestion to BigQuery

* When polling returns `200 OK`, parse the JSON manifest containing an array of resource types and pre-signed S3 download URLs.
* Map the `"type"` string of each output object directly to its corresponding BigQuery table name (e.g., `Patient` $\rightarrow$ `patient`).
* Iterate through all URLs. Note that a single resource type may contain multiple chunked files.
* **Memory Guardrail:** Use `requests.get(url, stream=True)` to stream the `.ndjson` payload over HTTP. Pass the raw file-like byte stream (`response.raw`) directly into the BigQuery SDK’s `client.load_table_from_file()` method. Do not download files to local disk or load entire files into memory.

#### 4. BigQuery Ingestion Configuration

Configure the BigQuery `LoadJobConfig` with the following parameters:

* `source_format = SourceFormat.NEWLINE_DELIMITED_JSON`
* `write_disposition = WriteDisposition.WRITE_APPEND`
* `autodetect = True` (Allows BigQuery to infer complex, nested `RECORD`/`STRUCT` structures and automatically initialize tables it hasn't seen before).
* `schema_update_options = [SchemaUpdateOption.ALLOW_FIELD_ADDITION]` (Enables automatic schema evolution when new fields or attributes appear in the FHIR JSON).

#### 5. Error Handling & Resiliency

* **HTTP error Handling:** If any endpoint returns an HTTP error status, terminate the task with a non-zero exit code so Kubernetes can retry it later.
* **Stateless Fault Tolerance:** Do not persist state inside the script or an external cache. If any exception occurs mid-stream, raise the error and crash the pod. The downstream Data Science team will handle de-duplication of overlapping data via SQL transformations (e.g., using `ROW_NUMBER() OVER (PARTITION BY id ORDER BY meta.lastUpdated DESC)`), meaning partial or duplicated loads are safe.

#### 6. Kubernetes Infrastructure Targets (For Deployment Reference)

* Packaged to run as a standard `CronJob`.
* Must explicitly enforce `concurrencyPolicy: Forbid` within the CronJob YAML specification to prevent concurrent executions from overlapping and calculating incorrect high-water marks.