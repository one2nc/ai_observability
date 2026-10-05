# Three-way comparison: OpenLLMetry vs OpenLIT vs Langfuse

Same agent, same tools, same dependency graph, same `max_turns=10`, three
observability stacks.

## Setup cost

| | OpenLLMetry (exp 6) | OpenLIT (exp 7) | Langfuse |
|---|---|---|---|
| Instrumentation code | `Traceloop.init()` | `openlit.init()` | ~200-line `TracingProcessor` bridge you maintain |
| Agent code changes | none | none | none (`clone()` for the managed prompt) |
| Backend deps | collector + any OTel sink | collector + any OTel sink | Langfuse (Postgres + ClickHouse + Redis + MinIO) |
| App knows the backend | no | no | **yes** |

## Coverage

| Capability | OpenLLMetry | OpenLIT | Langfuse |
|---|---|---|---|
| Agent / tool / model spans | Yes | Yes | Yes (via the bridge) |
| Prompt + completion text readable | Optional | Optional | Yes, first-class |
| Token usage visible | Yes | Yes | Yes |
| Cost | No | Yes (metric) | Yes (per trace, backend-computed) |
| `invoke_workflow` duration **metric** | No | Yes | **No** |
| `execute_tool` duration **metric** | No | Yes | **No** |
| Time to first token | No | Yes | No |
| PromQL / alerting on GenAI signals | Yes | Yes | **No** |
| Latency percentiles | Yes | Yes | Per-model charts only, not alertable |
| Logs | Yes (gateway) | Yes (gateway) | **No** |
| Session grouping of multi-turn runs | No | No | Yes |
| Per-user attribution | No | No | Yes |
| Prompt versioning, trace to version link | No | No | Yes |
| Human feedback scores | No | No | Yes |
| LLM-as-a-judge on production traces | No | No | Yes |
| Datasets + repeatable experiment runs | No | No | Yes |
| Regression diff between two runs | No | No | Yes |
| Sink-agnostic app code | Yes | Yes | **No** |

The table splits cleanly in half. Everything above "Session grouping" is
monitoring, and Langfuse loses or ties. Everything below is evaluation, and
Langfuse is the only one that has any of it.

## What each is actually for

**OpenLLMetry** is the weakest arm for agents, for the reason experiment 6
documented: the Agents instrumentor allocates workflow and tool duration
instruments but never calls `.record()`, so those panels stay empty and you close
the latency gap by opening a trace. It does emit
`gen_ai.client.generation.choices`, a decent proxy for tool-calling behaviour,
and it threads distributed tracing through Bifrost cleanly.

**OpenLIT** is the best pure-monitoring answer. Every latency, token and cost
question is answerable from metrics without opening a trace: what you want on a
dashboard someone watches at 3am. One line to install. It tells you nothing about
whether the agent is correct.

**Langfuse** is an evaluation tool that also stores traces. Sessions, prompt
versioning, scores, LLM-as-a-judge, datasets and run diffs have no equivalent in
either of the others, and they are what you need when the agent is up, fast,
cheap, and wrong. For an agent that matters more than it would for a plain RAG
endpoint: "up and fast" is table stakes, and "correct" is the actual product
risk.

## The three real costs

**1. No metrics, no alerts.** Not something you can instrument around. Anything
resembling an SLO needs a second backend.

**2. The app stops being sink-agnostic.** Every other experiment sends OTLP to
`:4418` and knows nothing about the backend. This one imports `langfuse`, calls
`get_prompt()` on the request path, and installs a Langfuse-specific trace
processor. Swapping Langfuse out means deleting code, not editing a collector
config.

That coupling is not avoidable by being cleverer. You can keep an app pure and
route traces through the gateway with `make up SINK=langfuse`; any of the other
experiments will land traces in Langfuse with zero code changes. What you get
that way is traces only: no prompt linkage, no scores, no datasets. The features
are the coupling.

**3. You own the instrumentation.** No Agents SDK auto-instrumentor means the
bridge is yours to maintain against two moving APIs. It is the cost least visible
in a feature comparison and the one most likely to bite on an upgrade.

## Recommendation

| If you need | Use |
|---|---|
| Dashboards and alerts on agent latency, tokens, cost | OpenLIT -> gateway -> Grafana/SigNoz |
| To know whether answer quality regressed after a change | Langfuse |
| Both, which is the usual honest answer for an agent in production | OpenLIT to the gateway **and** spans to Langfuse, accepting two backends |
| One vendor, already on Traceloop | OpenLLMetry, accepting the workflow/tool metric gap |

Do not read this as "Langfuse replaces OpenLIT". It replaces the part of your
workflow that is currently a spreadsheet of hand-checked answers.
