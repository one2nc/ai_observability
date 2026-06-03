.PHONY: up down ingest ask health logs

PORT ?= 8001

up:
	docker compose up --build

down:
	docker compose down

ingest:
	curl -s -X POST http://localhost:$(PORT)/ingest -F "file=@sample_data/kubernetes.txt" | python3 -m json.tool

ask:
	curl -s -X POST http://localhost:$(PORT)/ask -H "Content-Type: application/json" -d '{"query": "What does the kube-scheduler do?", "user_id": "saurabh"}' | python3 -m json.tool

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

logs:
	docker compose logs -f
