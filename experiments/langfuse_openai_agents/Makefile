.PHONY: build up down ask auth-ask payments-ask catalog-ask checkout-ask random-ask \
	session-ask feedback eval health logs langfuse-health traces

PORT ?= 8006
LANGFUSE_UI ?= http://localhost:3000
# Same defaults as the headless bootstrap in infra/sinks/langfuse.
LANGFUSE_PUBLIC_KEY ?= pk-lf-11111111-1111-4111-8111-111111111111
LANGFUSE_SECRET_KEY ?= sk-lf-22222222-2222-4222-8222-222222222222

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down --remove-orphans

ask:
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d '{"query":"Checkout errors started after a deploy. Triage the incident."}' | python3 -m json.tool

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

random-ask:
	@SERVICE=$$(echo "checkout payments catalog auth" | tr ' ' '\n' | sort -R | head -1); \
	echo "Querying service: $$SERVICE"; \
	curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d "{\"query\":\"$$SERVICE is showing errors. Triage the incident.\"}" | python3 -m json.tool

# Multi-turn session: two questions sharing one session_id, so Langfuse's
# Sessions view stitches them into a single conversation.
session-ask:
	@SESSION=triage-$$(date +%s); \
	echo "session_id: $$SESSION"; \
	for SVC in checkout payments; do \
		curl -s -X POST http://localhost:$(PORT)/ask \
			-H "Content-Type: application/json" \
			-d "{\"query\":\"$$SVC is showing errors. Triage the incident.\",\"session_id\":\"$$SESSION\"}" \
			| python3 -m json.tool; \
	done

# Asks a question, then scores the resulting trace thumbs-up. Demonstrates the
# trace-id handoff: /ask returns the ID, /feedback attaches a score to it.
feedback:
	@TRACE=$$(curl -s -X POST http://localhost:$(PORT)/ask \
		-H "Content-Type: application/json" \
		-d '{"query":"auth is showing errors. Triage the incident."}' \
		| python3 -c "import json,sys; print(json.load(sys.stdin)['trace_id'])"); \
	echo "trace_id: $$TRACE"; \
	curl -s -X POST http://localhost:$(PORT)/feedback \
		-H "Content-Type: application/json" \
		-d "{\"trace_id\":\"$$TRACE\",\"helpful\":true,\"comment\":\"clear triage report\"}" \
		| python3 -m json.tool

# Offline eval: runs the whole dataset through the live agent and uploads scores.
eval:
	docker compose --profile eval run --rm -T eval

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

langfuse-health:
	@curl -fsS $(LANGFUSE_UI)/api/public/health >/dev/null \
		&& echo "Langfuse reachable at $(LANGFUSE_UI)" \
		|| { echo "Langfuse NOT reachable — run 'make langfuse-up' in ../../infra"; exit 1; }

logs:
	docker compose logs -f

# Confirms spans actually landed. There are no metrics to check — Langfuse has
# no metrics store, which is the central finding of this experiment.
traces:
	@printf 'Traces in Langfuse: '
	@curl -fsS -u "$(LANGFUSE_PUBLIC_KEY):$(LANGFUSE_SECRET_KEY)" \
		"$(LANGFUSE_UI)/api/public/traces?limit=100" \
		| python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(len(d)); [print(' ', t.get('name'), t.get('sessionId'), t.get('userId')) for t in d[:5]]"
