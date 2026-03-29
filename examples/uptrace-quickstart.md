# Quickstart: Abidex + Uptrace for Persistent Traces

Copy-paste steps to run Uptrace locally and send Abidex traces to it. Uptrace uses **PostgreSQL** for metadata and **ClickHouse** for traces — a good fit if you prefer a relational DB for config and metadata.

## Step-by-step

### 1. Start Uptrace

**Option A — Docker run (single container):**

```bash
docker run -d -p 14317:4317 -p 14318:4318 \
  --name uptrace \
  -e UPTRACE_DSN=postgres://uptrace:uptrace@host.docker.internal:5432/uptrace \
  uptrace/uptrace:latest
```

*Note: This expects PostgreSQL at `host.docker.internal:5432`. For a full stack (Postgres + Uptrace), use Option B.*

**Option B — Docker Compose (recommended):**

See [Uptrace – Get started](https://uptrace.dev/get/) for the official `docker-compose` that includes PostgreSQL and Uptrace. Clone or copy the compose file, then:

```bash
docker compose up -d
```

Adjust the OTLP port in the compose if needed (e.g. `14317:4317` on the host).

### 2. Set the OTLP endpoint

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:14317
```

### 3. (Optional) Set service name

```bash
export OTEL_SERVICE_NAME=my-abidex-agent
```

### 4. Run your agent script

```bash
pip install abidex[otlp]
python examples/test-with-signoz.py
# or: python examples/crewai_simple.py
```

Traces are sent to Uptrace as your crew or graph runs.

### 5. Open the Uptrace UI

Open **http://localhost:14318** in your browser.

### 6. View traces

- **First time:** Sign up (first user becomes admin).
- Go to **Traces**.
- Search or filter by `service.name` (e.g. `my-abidex-agent`) or by Abidex attributes such as `gen_ai.agent.role`, `gen_ai.workflow.name`, `gen_ai.framework`.

## Troubleshooting

- **No traces in Uptrace** — Check Uptrace logs: `docker logs uptrace`. Ensure your script runs in the same environment where `OTEL_EXPORTER_OTLP_ENDPOINT` is set, and that you installed `abidex[otlp]`.
- **Port conflict** — Change the host port mapping (e.g. `-p 24317:4317 -p 24318:4318`) and set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:24317`.
- **Connection refused to localhost:14317** — Confirm the Uptrace container is running (`docker ps`) and that the OTLP gRPC port (4317 inside the container) is mapped to the host port you use.

## Note

Uptrace uses **PostgreSQL** for metadata and **ClickHouse** for trace data. See [docs/integration-and-testing.md](../docs/integration-and-testing.md) for backends.
