.PHONY: up down ingest ask random-ingest random-ask random-traffic health logs

PORT ?= 8004
COUNT ?= 5

build:
	docker compose build

up:
	docker compose up -d

logs:
	docker compose logs -f

down:
	docker compose down

ingest:
	curl -s -X POST http://localhost:$(PORT)/ingest -F "file=@sample_data/kubernetes.txt" | python3 -m json.tool

ask:
	curl -s -X POST http://localhost:$(PORT)/ask -H "Content-Type: application/json" -d '{"query": "What does the kube-scheduler do?", "user_id": "anonymous", "chat_model": "openrouter/gpt-4o-mini"}' | python3 -m json.tool

random-ingest:
	PORT=$(PORT) python3 ./scripts/random_rag.py ingest --count 1

random-ask:
	PORT=$(PORT) python3 ./scripts/random_rag.py ask --count 1

random-traffic:
	PORT=$(PORT) python3 ./scripts/random_rag.py traffic --count $(COUNT)

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

dashboard:
	curl -s -X POST http://localhost:3000/api/dashboards/db -H "Content-Type: application/json" -u admin:admin -d @dashboard.grafana.json | python3 -m json.tool
