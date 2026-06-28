# OpenAI Agents Observability: OpenLIT vs OpenLLMetry

This comparison uses the same FastAPI incident-triage agent in both experiments:

- `experiments/openlit_openai_agents`
- `experiments/openllmetry_openai_agents`

This document compares only the telemetry emitted by OpenLIT and OpenLLMetry.
HTTP server metrics in the experiment dashboards come from FastAPI/OpenTelemetry
instrumentation, not from either library, so they are not counted as OpenLIT or
OpenLLMetry capability here.

## Expected result

| Signal | OpenLIT, `responses` | OpenLIT, `chat_completions` | OpenLLMetry, `responses` | OpenLLMetry, `chat_completions` |
|---|---|---|---|---|
| Model-call duration, `chat` | Present | Present | Missing | Minimal |
| Token usage | Present | Present | Missing | Minimal |
| Agent workflow duration, `invoke_workflow` / `invoke_agent` | Present | Present | Missing | Missing |
| Tool duration, `execute_tool` | Present | Present | Missing | Missing |
| Agent/tool spans | Present | Present | Present | Present |
| Model-call spans | Present | Present | Present | Present |

The important gap is API-path dependent. With `OPENAI_AGENTS_API=responses`,
OpenLLMetry emits no GenAI metrics in this experiment. With
`OPENAI_AGENTS_API=chat_completions`, OpenLLMetry emits minimal model/token
metrics from the legacy chat-completions path, but still does not record OpenAI
Agents workflow, agent, or tool duration metrics. OpenLIT records the GenAI
metrics in both modes.

## GenAI Dashboard Panels

Both dashboards contain the same GenAI panels so missing series are visible
instead of hidden behind different dashboard layouts:

| # | Panel | Expected OpenLIT behavior | Expected OpenLLMetry behavior |
|---|---|---|---|
| 1 | Agent Workflow Duration p95 | Populates for `invoke_workflow` and `invoke_agent` | Empty |
| 2 | Tool Execution Duration p95 | Populates for `execute_tool` | Empty |
| 3 | Model Call Duration p95 | Populates for `chat` in both API modes | Empty in `responses`; minimal in `chat_completions` |
| 4 | Token Usage | Populates for input/output tokens in both API modes | Empty in `responses`; minimal in `chat_completions` |

The experiment dashboards also include HTTP panels as a control signal, but those
HTTP metrics are emitted by FastAPI/OpenTelemetry instrumentation and are not
part of this library comparison.

## Validation queries

Run these against Prometheus. In this repo's current setup Prometheus is commonly
available at `http://127.0.0.1:9091`.

### Operation duration coverage

```promql
sum by (service_name, gen_ai_operation_name) (
  gen_ai_client_operation_duration_seconds_count{
    service_name=~"ai-obs-openlit-openai-agents|ai-obs-openllmetry-openai-agents"
  }
)
```

Expected:

| Service | Expected operations |
|---|---|
| `ai-obs-openlit-openai-agents` | `invoke_workflow`, `invoke_agent`, `execute_tool`, `chat` |
| `ai-obs-openllmetry-openai-agents` in `responses` mode | No GenAI operation metrics expected |
| `ai-obs-openllmetry-openai-agents` in `chat_completions` mode | Minimal `chat` metrics may appear; `invoke_workflow`, `invoke_agent`, and `execute_tool` should be absent |

### Token usage

```promql
sum by (service_name, gen_ai_token_type, gen_ai_request_model) (
  gen_ai_client_token_usage_sum{
    service_name=~"ai-obs-openlit-openai-agents|ai-obs-openllmetry-openai-agents"
  }
)
```

Expected:

| Service | Expected behavior |
|---|---|
| `ai-obs-openlit-openai-agents` | Input/output token series are present in both API modes |
| `ai-obs-openllmetry-openai-agents` in `responses` mode | No token metric series expected |
| `ai-obs-openllmetry-openai-agents` in `chat_completions` mode | Minimal token metric series may appear |

## Practical conclusion

OpenLIT is the stronger option for this OpenAI Agents use case when the required
view is workflow, agent, tool, model, and token telemetry from the instrumentation
library itself. OpenLLMetry still gives useful traces, and can expose minimal
model/token metrics on the legacy chat-completions path, but the Responses path
has no GenAI metrics here and the missing agent/workflow/tool metric series limit
dashboarding and alerting for agent SLOs.
