# Manual tool-loop agent with hand-rolled OTel

## Context: from RAG to agents

Experiments 1-4 instrument a **RAG pipeline** - embed a query, search a vector
database, pass retrieved context to a model, return an answer. The observable
steps are: embedding call, vector search, and generation call.

This experiment shifts to an **agentic pattern**. Instead of retrieving context
from a database, the model decides at runtime which **tools** (functions) to call,
inspects their results, and may loop multiple times before producing a final answer.

The observable steps change:

| RAG pipeline (experiments 1-4) | Agent tool loop (experiments 5-7) |
|---|---|
| Embedding call | Model call (decides which tools to use) |
| Vector search | Tool execution (e.g. check service health) |
| Generation call | Tool execution (e.g. lookup runbook) |
| - | Model call (synthesizes final answer) |
| Single pass, predictable | Multi-turn, model-driven |

New terminology for agent observability:

| Concept | What it means | Why you measure it |
|---|---|---|
| **Workflow** | The entire agent run from question to final answer | End-to-end SLO - "how long did the user wait?" |
| **Tool call** | A function the model chose to invoke (e.g. `check_service_health`) | Identify slow/failing external dependencies |
| **Model call** (chat) | A single round-trip to the LLM API | Provider latency, token cost per turn |
| **Turn** | One iteration of the loop: model call → tool calls → next model call | Detect runaway loops that inflate cost |

## What this experiment does

**The problem:** In an agent, the model controls the execution flow - it decides
which tools to call, how many times, and in what order. A simple request (auth)
completes in 1 turn. A complex request (checkout) triggers 4+ turns as the model
follows dependency chains, with slow tools like `ledger` (1.5s) dominating latency.

The agent has access to a service dependency graph with simulated latencies:

```
checkout (0.5s)
├── payments (0.3s)
│   └── ledger (1.5s)
├── catalog (0.2s)
│   ├── search-index (0.8s)
│   └── inventory (0.1s)
└── auth (0.1s)
```

The code sets `max_turns=4`. Different services exercise different turn counts:

| Target | Service | Dependencies | Expected turns | Result |
|---|---|---|---|---|
| `make auth-ask` | auth | none | 1 | Completes immediately |
| `make payments-ask` | payments | ledger | 2 | Checks payments, then ledger |
| `make catalog-ask` | catalog | search-index, inventory | 3 | Checks catalog, then both deps |
| `make checkout-ask` | checkout | payments, catalog, auth | 4+ | Hits max_turns, gets cut off |

When the user asks about catalog, the model follows the dependency chain (3 turns):

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent loop
    participant M as Model API
    participant T as Tools

    U->>A: "catalog is showing errors. Triage."
    Note over A: Turn 1
    A->>M: chat.completions.create (query + tools schema)
    M-->>A: tool_calls: [check_service_health, lookup_runbook, check_dependencies]
    A->>T: check_service_health("catalog")
    T-->>A: {"status": "degraded", "error_rate": 0.05}
    A->>T: lookup_runbook("catalog")
    T-->>A: "Check cache hit rate and database replica lag."
    A->>T: check_dependencies("catalog") [0.2s]
    T-->>A: dependencies: [search-index, inventory]
    Note over A: Turn 2
    A->>M: chat.completions.create (tool results)
    M-->>A: tool_calls: [check_service_health x2, check_dependencies x2]
    A->>T: check_service_health("search-index")
    T-->>A: {"status": "degraded", "error_rate": 0.12}
    A->>T: check_service_health("inventory")
    T-->>A: {"status": "healthy"}
    A->>T: check_dependencies("search-index") [0.8s]
    T-->>A: dependencies: []
    A->>T: check_dependencies("inventory") [0.1s]
    T-->>A: dependencies: []
    Note over A: Turn 3
    A->>M: chat.completions.create (tool results)
    M-->>A: Final triage report (no more tool_calls)
    A-->>U: severity, evidence, next actions
```

For checkout (4+ turns), the model must also explore payments (→ ledger) and
auth before it can synthesize, which exceeds `max_turns=4` and gets cut off.

If all you have is the HTTP-level
metric ("this request took 20 seconds"), you can't tell whether the bottleneck
is the model, a tool, or a runaway multi-turn loop.

**The solution in this experiment:** Build the tool loop by hand using the raw
OpenAI chat completions API, and wrap every step with manual OTel spans and
metrics. No Agents framework, no auto-instrumentation library - you write
both the loop and the instrumentation.

Because **you own the loop**, you can wrap every step with spans and metrics:

```python
with tracer.start_as_current_span("invoke_workflow"):
    while True:
        with tracer.start_as_current_span("chat"):
            response = await client.chat.completions.create(...)
            duration_histogram.record(elapsed, {"operation": "chat"})

        for call in response.tool_calls:
            with tracer.start_as_current_span("execute_tool"):
                result = dispatch(call)
                duration_histogram.record(elapsed, {"operation": "execute_tool"})
```

The result: **all six dashboard panels populate** - workflow duration, tool latency,
model-call duration, token usage, HTTP traffic, and HTTP latency. This is the
observability baseline.

Experiments 6 and 7 replace the manual loop with the OpenAI Agents SDK (less
code, same behavior) and test whether instrumentation libraries can reproduce
this visibility automatically.

## Expected trace

| # | Span | Parent | Duration | Source | What it tells you | Sample attributes |
|---|---|---|---|---|---|---|
| 1 | `POST /ask` | - | variable | FastAPI auto | End-to-end user latency | `http.target=/ask`, `http.status_code=200` |
| 2 | `invoke_workflow` | `POST /ask` | variable | Manual span | Total agent run including all turns | `gen_ai.operation.name=invoke_workflow`, `gen_ai.request.model` |
| 3 | `chat` | `invoke_workflow` | variable | Manual span | First model call (decides to use tools) | `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| 4 | `execute_tool` | `invoke_workflow` | variable | Manual span | check_service_health call | `gen_ai.tool.name=check_service_health` |
| 5 | `execute_tool` | `invoke_workflow` | variable | Manual span | lookup_runbook call | `gen_ai.tool.name=lookup_runbook` |
| 6 | `chat` | `invoke_workflow` | variable | Manual span | Final synthesis turn | `gen_ai.response.model`, token usage |

## Span attributes

| Attribute | Example | What it tells you |
|---|---|---|
| `gen_ai.operation.name` | `invoke_workflow`, `chat`, `execute_tool` | Operation category |
| `gen_ai.request.model` | `gpt-4.1-mini` | Requested model |
| `gen_ai.response.model` | `gpt-4.1-mini-2025-04-14` | Actual model used |
| `gen_ai.usage.input_tokens` | `418` | Prompt tokens for this turn |
| `gen_ai.usage.output_tokens` | `96` | Generated tokens for this turn |
| `gen_ai.tool.name` | `lookup_runbook` | Which tool was called |
| `gen_ai.tool.result_length` | `87` | Tool response size |

## Metrics dashboard

Import `dashboards/dashboard.grafana.json` from Grafana's dashboard import UI.

For API import:

```bash
make dashboard
```

All six panels should populate - this is the baseline for "what full observability
looks like."

| Panel | Metric | PromQL | What it tells you |
|---|---|---|---|
| Agent Workflow Duration p95 | `gen_ai.client.operation.duration` | `histogram_quantile(0.95, sum(increase(gen_ai_client_operation_duration_seconds_bucket{service_name="ai-obs-openai-agents-manual",gen_ai_operation_name="invoke_workflow"}[$__range])) by (le))` | Total agent run latency |
| Tool Execution Duration p95 | `gen_ai.client.operation.duration` | `histogram_quantile(0.95, sum(increase(gen_ai_client_operation_duration_seconds_bucket{service_name="ai-obs-openai-agents-manual",gen_ai_operation_name="execute_tool"}[$__range])) by (le))` | Tool latency |
| Model Call Duration p95 | `gen_ai.client.operation.duration` | `histogram_quantile(0.95, sum(increase(gen_ai_client_operation_duration_seconds_bucket{service_name="ai-obs-openai-agents-manual",gen_ai_operation_name="chat"}[$__range])) by (le, gen_ai_request_model))` | Provider latency |
| Token Usage | `gen_ai.client.token.usage` | `sum(increase(gen_ai_client_token_usage_sum{service_name="ai-obs-openai-agents-manual"}[$__range])) by (gen_ai_token_type, gen_ai_request_model)` | Token consumption |
| HTTP Requests | `http.server.duration` | `sum(increase(http_server_duration_milliseconds_count{service_name="ai-obs-openai-agents-manual",http_target="/ask"}[$__range])) by (http_status_code)` | Traffic volume |
| HTTP Request Duration p95 | `http.server.duration` | `histogram_quantile(0.95, sum(increase(http_server_duration_milliseconds_bucket{service_name="ai-obs-openai-agents-manual",http_target="/ask"}[$__range])) by (le))` | User-visible latency |

## Failure modes

| # | Failure mode | Why? | How? | Where? | What? |
|---|---|---|---|---|---|
| 1 | Slow conversation | Multiple model turns dominate total latency | Alert when workflow p95 exceeds threshold | Agent Workflow Duration p95 panel | `gen_ai_client_operation_duration_seconds{gen_ai_operation_name="invoke_workflow"}` |
| 2 | Slow tool | External tool dominates total latency | Alert when tool p95 exceeds threshold | Tool Execution Duration p95 panel | `gen_ai_client_operation_duration_seconds{gen_ai_operation_name="execute_tool"}` |
| 3 | Slow provider | Model calls dominate total latency | Compare model p95 with workflow p95 | Model Call Duration p95 panel | `gen_ai_client_operation_duration_seconds{gen_ai_operation_name="chat"}` |
| 4 | Token cost spike | Runaway context or loops increase spend | Alert when token rate exceeds budget | Token Usage panel | `gen_ai_client_token_usage{gen_ai_token_type="input\|output"}` |
| 5 | Runaway turns | Model loops inflate cost and latency | chat count growing faster than http_requests count | Operation Count panel | `gen_ai_client_operation_duration_seconds_count{gen_ai_operation_name="chat"}` vs `http_server_duration_milliseconds_count` |
| 6 | Tool failure | Tool returns error, agent cannot triage | Filter spans by error status | Trace explorer | `execute_tool` span with `otel.status_code=ERROR` |
| 7 | Provider error | OpenAI returns 5xx/timeout | Filter error traces and HTTP status | Trace explorer + HTTP Requests panel | `chat` span exception + `http_server_duration_milliseconds_count{http_status_code=~"5.."}` |
| 8 | App saturation | Concurrent requests queue up | HTTP p95 rises while model p95 stays flat | HTTP Request Duration p95 panel | `http_server_duration_milliseconds_bucket` |
| | **Not detectable (needs eval layer)** | | | | |
| 9 | Model quality degradation | Bad answers despite correct tools | - | - | Needs eval layer |
| 10 | Tool returns wrong data | Synthetic tools always "work" | - | - | Needs integration testing |

## Usage

```bash
cd ../../infra
make up

cd ../experiments/openai_agents_manual
cp .env.example .env
# Set OPENAI_API_KEY

make up
```

From another terminal:

```bash
make auth-ask           # 1 turn - no dependencies
make payments-ask       # 2 turns - checks ledger
make catalog-ask        # 3 turns - checks search-index, inventory
make checkout-ask       # 4+ turns - hits max_turns, gets cut off
make random-ask         # random service each time
make metrics
make dashboard
```

## What to read next

- [Experiment 6: OpenLLMetry + OpenAI Agents](../openllmetry_openai_agents/README.md) - same agent with the Agents SDK; metrics disappear
- [Experiment 7: OpenLIT + OpenAI Agents](../openlit_openai_agents/README.md) - same agent with the Agents SDK; metrics restored

## Appendix: Metric dimensions

### `gen_ai.client.operation.duration`

| Dimension | Example |
|---|---|
| `gen_ai_operation_name` | `invoke_workflow`, `chat`, `execute_tool` |
| `gen_ai_request_model` | `gpt-4.1-mini` |
| `gen_ai_tool_name` | `check_service_health`, `lookup_runbook` |
| `service_name` | `ai-obs-openai-agents-manual` |

### `gen_ai.client.token.usage`

| Dimension | Example |
|---|---|
| `gen_ai_operation_name` | `chat` |
| `gen_ai_request_model` | `gpt-4.1-mini` |
| `gen_ai_token_type` | `input`, `output` |
| `service_name` | `ai-obs-openai-agents-manual` |

### HTTP metrics

| Dimension | Example |
|---|---|
| `http_method` | `POST` |
| `http_target` | `/ask` |
| `http_status_code` | `200` |
| `service_name` | `ai-obs-openai-agents-manual` |
