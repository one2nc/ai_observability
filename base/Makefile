.PHONY: setup infra infra-down run ingest ask health clean

PORT ?= 8001

setup:
	uv sync

infra:
	docker compose up -d

infra-down:
	docker compose down

run:
	uv run python app.py

ingest:
	curl -s -X POST http://localhost:$(PORT)/ingest -F "file=@sample_data/kubernetes.txt" | python3 -m json.tool

ask:
	curl -s -X POST http://localhost:$(PORT)/ask -H "Content-Type: application/json" -d '{"query": "What does the kube-scheduler do?"}' | python3 -m json.tool

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

clean:
	docker compose down -v
