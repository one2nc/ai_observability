.PHONY: build up down ask random-ask auth-ask payments-ask catalog-ask checkout-ask health logs metrics dashboard

PORT ?= 8003
PROMETHEUS_URL ?= http://127.0.0.1:9091

build:
	docker compose build

up:
	docker compose up -d

logs:
	docker compose logs -f

down:
	docker compose down

ask:
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d '{"query":"Checkout errors started after a deploy. Triage the incident."}' | python3 -m json.tool

random-ask:
	@SERVICE=$$(echo "checkout payments catalog auth" | tr ' ' '\n' | sort -R | head -1); \
	echo "Querying service: $$SERVICE"; \
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d "{\"query\":\"$$SERVICE is showing errors. Triage the incident.\"}" | python3 -m json.tool

auth-ask:
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d '{"query":"auth is showing errors. Triage the incident."}' | python3 -m json.tool

payments-ask:
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d '{"query":"payments is showing errors. Triage the incident."}' | python3 -m json.tool

catalog-ask:
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d '{"query":"catalog is showing errors. Triage the incident."}' | python3 -m json.tool

checkout-ask:
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d '{"query":"checkout is showing errors and high latency. Triage the incident."}' | python3 -m json.tool

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

logs:
	docker compose logs -f

metrics:
	curl -sG "$(PROMETHEUS_URL)/api/v1/label/__name__/values" | python3 -m json.tool

dashboard:
	curl -s -X POST http://127.0.0.1:3000/api/dashboards/db \
		-H "Content-Type: application/json" \
		-u admin:admin \
		--data-binary @dashboards/dashboard.api.json | python3 -m json.tool
