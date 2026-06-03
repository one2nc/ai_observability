.PHONY: up down status clean check-signoz-traces check-signoz-logs check-signoz-metrics

SINK ?= signoz
SIGNOZ_COMPOSE_DIR := .vendor/signoz/deploy/docker
SIGNOZ_OVERRIDE := sinks/signoz/docker-compose.yml

up: sink-up
	cd postgres && docker compose up -d
	cd otel-collector-gateway && docker compose up

down:
	cd otel-collector-gateway && docker compose down
	cd postgres && docker compose down
	$(MAKE) sink-down

sink-up:
ifeq ($(SINK),signoz)
	cd sinks/signoz && ./bootstrap.sh
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose -f docker-compose.yaml -f ../../../../$(SIGNOZ_OVERRIDE) up -d
endif

sink-down:
ifeq ($(SINK),signoz)
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose -f docker-compose.yaml -f ../../../../$(SIGNOZ_OVERRIDE) down
endif

status:
	cd postgres && docker compose ps
	cd otel-collector-gateway && docker compose ps
ifeq ($(SINK),signoz)
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose ps
endif

clean:
	cd otel-collector-gateway && docker compose down -v
	cd postgres && docker compose down -v
ifeq ($(SINK),signoz)
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose -f docker-compose.yaml -f ../../../../$(SIGNOZ_OVERRIDE) down -v
endif

check-signoz-traces:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT count() as total_spans FROM signoz_traces.signoz_index_v3"

check-signoz-logs:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT count() as total_logs FROM signoz_logs.logs_v2"

check-signoz-metrics:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT DISTINCT metric_name FROM signoz_metrics.distributed_samples_v4 ORDER BY metric_name"
