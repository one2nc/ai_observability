.PHONY: setup infra app app-down ingest ask health

PORT ?= 8001

infra:
	$(MAKE) -C ../../infra up

app:
	docker compose up --build

app-down:
	docker compose down

ingest:
	curl -s -X POST http://localhost:$(PORT)/ingest -F "file=@sample_data/kubernetes.txt" | python3 -m json.tool

ask:
	curl -s -X POST http://localhost:$(PORT)/ask -H "Content-Type: application/json" -d '{"query": "What does the kube-scheduler do?"}' | python3 -m json.tool

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

logs:
	docker compose logs -f app
