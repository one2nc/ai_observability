.PHONY: build up down ask logs health traces \
	stage-0 stage-1 stage-2 stage-3 stage-4 stage-5 stage-7 run-all

LANGFUSE_HOST ?= http://localhost:3400
# Same defaults as the headless bootstrap in infra/sinks/langfuse.
LANGFUSE_PUBLIC_KEY ?= pk-lf-11111111-1111-4111-8111-111111111111
LANGFUSE_SECRET_KEY ?= sk-lf-22222222-2222-4222-8222-222222222222

RUN := docker compose run --rm stage
RUN_T := docker compose run --rm -T stage

STAGE_0 := src/stage_0_plain_bot.py
STAGE_1 := src/stage_1_tracing.py
STAGE_2 := src/stage_2_sessions.py
STAGE_3 := src/stage_3_nested_spans.py
STAGE_4 := src/stage_4_prompt_mgmt.py
STAGE_5 := src/stage_5_user_feedback.py
STAGE_7 := src/stage_7_datasets_experiments.py
# Stages 6 and 8 are UI-only (Evaluators, Playground) — see the README.
INTERACTIVE_STAGES := $(STAGE_0) $(STAGE_1) $(STAGE_2) $(STAGE_3) $(STAGE_4) $(STAGE_5)

build:
	docker compose build

# There is no long-running service here — `up` builds the image and checks that
# the Langfuse stack in infra/ is actually reachable before you start a stage.
up: build health
	@echo
	@echo "Ready. Run a stage:  make stage-1   (see README for the full list)"

down:
	docker compose down --remove-orphans

health:
	@curl -fsS $(LANGFUSE_HOST)/api/public/health >/dev/null \
		&& echo "Langfuse reachable at $(LANGFUSE_HOST)" \
		|| { echo "Langfuse NOT reachable at $(LANGFUSE_HOST) — run 'make langfuse-up' in ../../infra"; exit 1; }

# Non-interactive smoke turn: one question through the nested-span stage, which
# produces a full chat-turn -> retrieve-context -> llm-response trace.
ask:
	@printf 'How do I get a refund?\nquit\n' | $(RUN_T) $(STAGE_3)

stage-0:
	$(RUN) $(STAGE_0)

stage-1:
	$(RUN) $(STAGE_1)

stage-2:
	$(RUN) $(STAGE_2)

stage-3:
	$(RUN) $(STAGE_3)

stage-4:
	$(RUN) $(STAGE_4)

stage-5:
	$(RUN) $(STAGE_5)

stage-7:
	$(RUN) $(STAGE_7)

# Every stage end to end, non-interactive. Stages 0-5 read stdin, so feed them a
# canned conversation; stage 7 runs the dataset experiment and exits.
run-all:
	@for s in $(INTERACTIVE_STAGES); do \
		echo "=== $$s ==="; \
		printf 'How do I get a refund?\nWhat are your support hours?\nquit\n' \
			| $(RUN_T) $$s || exit 1; \
	done
	@echo "=== $(STAGE_7) ==="
	@$(RUN_T) $(STAGE_7)

# Confirms spans actually landed. Langfuse has no metrics store, so there is no
# `make metrics` or `make dashboard` here.
traces:
	@printf 'Traces in Langfuse: '
	@curl -fsS -u "$(LANGFUSE_PUBLIC_KEY):$(LANGFUSE_SECRET_KEY)" \
		"$(LANGFUSE_HOST)/api/public/traces?limit=100" \
		| python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(len(d)); [print(' ', t.get('name'), t.get('sessionId'), t.get('userId')) for t in d[:5]]"

logs:
	docker compose logs -f
