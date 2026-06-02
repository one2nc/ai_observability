.PHONY: up down status clean bootstrap

SIGNOZ_DIR := .vendor/signoz/deploy/docker
COMPOSE := docker compose -f $(SIGNOZ_DIR)/docker-compose.yaml -f docker-compose.yml

up: $(SIGNOZ_DIR)/docker-compose.yaml
	$(COMPOSE) up

down:
	$(COMPOSE) down

$(SIGNOZ_DIR)/docker-compose.yaml:
	./bootstrap_signoz.sh

status:
	$(COMPOSE) ps

clean:
	$(COMPOSE) down -v

check-signoz-traces:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT count() as total_spans FROM signoz_traces.signoz_index_v3"

check-signoz-logs:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT count() as total_logs FROM signoz_logs.logs_v2"

check-signoz-metrics:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT DISTINCT metric_name FROM signoz_metrics.distributed_samples_v4 ORDER BY metric_name"
