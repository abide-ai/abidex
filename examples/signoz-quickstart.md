# SigNoz quickstart (local Docker)

Copy-paste instructions to run SigNoz locally for persistent traces and a UI. See [docs/integration-and-testing.md](../docs/integration-and-testing.md) for backends.

## Prerequisites

- Docker and Docker Compose
- Git

## Run SigNoz

```bash
git clone -b main https://github.com/SigNoz/signoz.git
cd signoz/deploy/
docker-compose -f docker/clickhouse-setup/docker-compose.yaml up -d
```

Wait for all services to be healthy (usually 1–2 minutes). Check with:

```bash
docker-compose -f docker/clickhouse-setup/docker-compose.yaml ps
```

## Access the UI

Open **http://localhost:3301** in your browser. On first visit you’ll go through signup; create an account to log in.

## Stop SigNoz

From the same directory:

```bash
cd signoz/deploy/
docker-compose -f docker/clickhouse-setup/docker-compose.yaml down
```

To remove volumes as well (delete trace data):

```bash
docker-compose -f docker/clickhouse-setup/docker-compose.yaml down -v
```

## Persistence

- **Default:** Data is stored in Docker volumes. It survives `docker-compose down` and container restarts. Only `down -v` removes it.
- **Host persistence (optional):** To keep data on the host, add a volume mount in the compose file for the ClickHouse data directory, or use a named volume and back it up. Example override (adjust paths to your setup):

  ```yaml
  # save as docker-compose.override.yaml in the same directory
  version: "3"
  services:
    clickhouse:
      volumes:
        - ./clickhouse-data:/var/lib/clickhouse
  ```

  Then run `docker-compose -f docker/clickhouse-setup/docker-compose.yaml up -d` as before.

## Next step: send Abidex traces to SigNoz

See [docs/integration-and-testing.md](../docs/integration-and-testing.md). In short:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
pip install abidex[otlp]
python your_agent_script.py
```

Traces will show up in the SigNoz UI under **Traces**.
