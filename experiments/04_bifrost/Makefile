.PHONY: up down ingest ask random-ingest random-ask random-traffic health logs

PORT ?= 8004
COUNT ?= 5

up:
	docker compose up --build

down:
	docker compose down

ingest:
	curl -s -X POST http://localhost:$(PORT)/ingest -F "file=@sample_data/kubernetes.txt" | python3 -m json.tool

ask:
	curl -s -X POST http://localhost:$(PORT)/ask -H "Content-Type: application/json" -d '{"query": "What does the kube-scheduler do?", "user_id": "anonymous", "chat_model": "openrouter/gpt-4o-mini"}' | python3 -m json.tool

random-ingest:
	PORT=$(PORT) ./scripts/random_rag.sh ingest 1

random-ask:
	PORT=$(PORT) ./scripts/random_rag.sh ask 1

random-traffic:
	PORT=$(PORT) ./scripts/random_rag.sh traffic $(COUNT)

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

logs:
	docker compose logs -f
