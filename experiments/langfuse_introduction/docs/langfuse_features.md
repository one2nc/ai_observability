# Langfuse features and trace structure

This document explains the Langfuse concepts used by
`experiments/langfuse_introduction` and maps them to the concrete traces emitted
by the stage scripts in `src/`.

## Feature theory and use cases

Langfuse is not just a trace viewer. Its strongest features sit around the LLM
product loop: observe a run, understand the conversation context, change the
prompt, collect quality labels, then evaluate changes against repeatable data.

| Feature | Theory | Example use case in this experiment |
|---|---|---|
| Traces | A trace is one logical user interaction. It records latency, inputs, outputs, model metadata, token usage and nested steps. | Stage 1 records each support-bot turn as `chat-turn`, so you can inspect exactly what the model saw and returned. |
| Generations | A generation is the LLM-specific child observation inside a trace. It carries the model, messages, output and token usage that drive cost. | `llm-response` shows whether the answer changed because the prompt changed, the model changed, or the input context changed. |
| Spans | Spans represent non-LLM work around the model call, such as retrieval, tools, guards or rerankers. | Stage 3 adds `retrieve-context`, making it obvious whether bad answers came from missing context or the generation itself. |
| Sessions | Sessions group multiple traces into one conversation or workflow. They answer questions a single trace cannot. | Stage 2 uses one `session_id` per CLI run, so Langfuse can replay the full chat instead of isolated turns. |
| Users | User IDs let you segment behavior and quality by customer, tenant, plan or internal tester. | The demo tags everything as `demo-user`; a real support bot would use account/user IDs to debug account-specific failures. |
| Prompt Management | Prompts become versioned runtime configuration instead of hardcoded strings. Traces link back to the prompt version used. | Stage 4 fetches `support-system-prompt` from Langfuse; edit it in the UI and compare traces without rebuilding the app. |
| Scores | Scores are quality labels attached to traces or observations. They can come from humans, code, or evaluator jobs. | Stage 5 writes a `user-feedback` BOOLEAN score, turning subjective feedback into filterable data. |
| LLM-as-a-Judge | A managed evaluator uses another model to score trace quality at scale. It is useful, but it creates extra model calls and cost. | Stage 6 can judge whether support answers are grounded, concise and helpful on newly arriving traces. |
| Datasets | A dataset is a stable set of inputs and expected outputs for repeatable evaluation. | Stage 7 creates `support-qa` with known support questions and expected substrings. |
| Experiments | Experiments run a task over a dataset and compare scored runs across prompt/model/code changes. | Run Stage 7 before and after changing the prompt or model, then compare `contains-expected` and `concise` scores. |
| Playground | Playground is the manual iteration surface for prompt/model experiments from a trace. | Open a weak trace, try a different instruction or model, then promote the better prompt into Prompt Management. |

## Trace and span structure

Langfuse stores this experiment as a small hierarchy of observations. The exact
shape changes by stage, but the important pattern is stable:

```text
trace: chat-turn
  input: conversation history or current question
  output: final assistant reply
  session_id: chat-<random>
  user_id: demo-user
  tags: stage-specific labels

  span: retrieve-context                 # Stage 3 only
    input: {"query": "<latest user text>"}
    output: {"hits": [...], "n": 0|1}
    purpose: non-LLM retrieval work

  generation: llm-response
    model: gpt-4o-mini or MODEL_NAME
    input: OpenAI-style messages
    output: assistant text
    usage_details: {"input": <tokens>, "output": <tokens>}
    prompt: support-system-prompt version # Stage 4 only

score: user-feedback                      # Stage 5 only
  trace_id: current chat-turn trace
  data_type: BOOLEAN
  value: 1 or 0
  comment: thumbs up / thumbs down

dataset: support-qa                       # Stage 7 only
  item.input: {"question": "..."}
  item.expected_output: {"must_contain": "..."}
  run: support-bot-eval / run-<MODEL_NAME>
  scores: contains-expected, concise
```

How to read it in the UI:

| UI field | Comes from | Why it matters |
|---|---|---|
| Trace name | `@observe(name="chat-turn")` | Defines the unit of analysis: one support turn. |
| Observation type | `as_type="span"` / `as_type="generation"` | Separates ordinary app work from LLM calls. |
| Parent/child tree | active Langfuse/OTel context | Shows whether latency or failure came from retrieval or generation. |
| Input/output | `input=...`, `gen.update(output=...)`, return value | Lets you debug exact prompt, context and answer. |
| Token usage | `usage_details` | Explains cost changes and prompt-size regressions. |
| Prompt version | `prompt=prompt_client` | Connects a trace to the managed prompt version used at runtime. |
| Session/user | `propagate_attributes(...)` | Groups traces into conversations and user cohorts. |
| Scores | `create_score(...)` or experiment evaluators | Turns qualitative quality into comparable numbers. |

## Evaluator examples

For Stage 6, start narrow. A useful LLM-as-a-judge evaluator for this support
bot should judge the final answer, not every observation:

```text
Evaluate the support assistant answer.

Score 1 if the answer is grounded in the user question, concise, helpful, and
does not invent unsupported policy details.

Score 0 if it is vague, too long, contradicts the known support policy, or makes
up facts.

Input:
{{input}}

Output:
{{output}}

Return a numeric score from 0 to 1 and a short reason.
```

Recommended mapping:

| Evaluator variable | Langfuse field |
|---|---|
| `input` | trace input |
| `output` | trace output |

Run it first on a filtered set of traces or on dataset experiment outputs. A
live evaluator with broad filters creates extra model calls for every matching
trace and can make cost climb quickly.
