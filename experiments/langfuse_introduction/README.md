# Langfuse hello world

A tour of Langfuse, one feature per stage, against the self-hosted Langfuse
stack in [`infra/sinks/langfuse/`](../../infra/sinks/langfuse/README.md). Each
stage is a runnable file that adds exactly one thing to the same small support
chatbot, so you can feel why the feature exists before moving on.

This is an introduction to Langfuse. It deliberately does not
use the shared RAG app or the OTel collector gateway. Instead it walks through
the Langfuse concepts (traces, sessions, prompts, scores, datasets) one at a
time, so they are familiar when you need them later.

Runs with no LLM API key: a deterministic mock model is built in, which also
makes traces reproducible. Set `OPENAI_API_KEY` for real calls.

You type a question, the bot answers, and Langfuse records what happened.

Each stage adds one layer to that loop: a trace, then sessions, then nested
spans, and so on.

## The stages

### Stage 0: plain bot

No instrumentation. You see only what you `print`.

**Catches:** nothing. This is the blindness the rest of the tour fixes.

### Stage 1: tracing

Every turn becomes one trace that records the model call: input messages, reply,
token usage, latency and cost. Stage 0 showed nothing; now every turn is captured.

**Catches:**
- Slow model (provider latency on the response).
- Token or cost spike (a prompt change blew up input size).
- Missing traces when a short script dies before flushing.
- Wrong instance keys (401s that look like an outage).

### Stage 2: sessions and users

Each turn is tagged with a session and a user, so Langfuse can replay a whole
conversation in order and filter traces down to one person.

**Catches:**
- Broken conversation flow (turn 4 contradicts turn 2).

### Stage 3: nested spans

Before answering, the bot now looks up relevant snippets from a small knowledge
base and feeds them to the model (a basic RAG flow), so one turn has two timed
sub-steps nested under it: the lookup and the model call.

**Catches:**
- Slow retrieval (the lookup sub-step is the slow one, not the model).
- Retrieval returns nothing (empty context, so bad answers).

### Stage 4: prompt management

The system prompt lives in Langfuse, and each trace records which prompt version
produced it. Edit the prompt in the UI, save a new version, run again, no code change.

**Catches:**
- A prompt edit made things worse (compare traces by prompt version).

### Stage 5: scores

Rate each reply thumbs up or down. The score attaches to that reply's trace and
aggregates across many of them in Dashboards.

**Catches:**
- Bad answer quality, graded by hand.

### Stage 6: LLM-as-a-judge (UI only)

No code. In **Evaluators**, add a managed judge and point it at the project's
traces; it auto-scores new traces as they arrive. Needs an LLM provider key in
Langfuse settings for the judge model.

**Catches:**
- Bad answer quality, graded automatically with no human in the loop.

### Stage 7: datasets and experiments

The offline eval loop, and the payoff stage. You save a fixed set of test
questions, run each through the bot, and score every answer automatically
(expected keyword present, answer concise). Change the prompt or model, run
again, and compare the two runs side by side in **Datasets → support-qa → Runs**.

**Catches:**
- A model swap made things worse (diff two runs on the same questions).
- A prompt regression again, this time offline instead of on live traffic.

### Stage 8: playground (UI only)

When a trace looks bad, open it and jump into the Playground to iterate on
prompt and model without leaving Langfuse. Self-hosted includes it; the Cloud
free tier omits it.

**Catches:** nothing new. It's the fix-it bench, not a detector.

## Observation attributes

All of these are set by our code. There is no auto-instrumentation in this
experiment.

| Attribute | Set by | Example | What it tells you |
|---|---|---|---|
| `name` | `@observe` / `start_as_current_observation` | `chat-turn`, `llm-response` | Step identity |
| `session_id` | `propagate_attributes` | `chat-a1b2c3d4` | Groups turns into a conversation |
| `user_id` | `propagate_attributes` | `demo-user` | Per-user attribution |
| `tags` | `propagate_attributes` | `["stage-3", "rag"]` | Filtering in the UI |
| `model` | generation kwarg | `gpt-4o-mini` | Which model was asked |
| `input` / `output` | generation kwarg / `update()` | message list / reply text | Exact prompt and completion |
| `usage_details` | `update()` | `{"input": 42, "output": 18}` | Token counts, which drive cost |
| `prompt` | generation kwarg (stage 4) | `support-system-prompt` v2 | Links the trace to a prompt version |
| score `user-feedback` | `create_score` (stage 5) | `1` / `0`, BOOLEAN | Human quality signal |


## Usage

All paths are relative to this experiment folder
(`experiments/langfuse_introduction`). The Langfuse stack lives in the repo-root
`infra/` folder, two levels up, and has its own Makefile.

Start Langfuse once, from `infra/`:

```bash
cd ../../infra         # repo-root infra, not a folder inside this experiment
make langfuse-up
make langfuse-keys     # prints the credentials shown below
```

Then come back here and build:

```bash
cd ../../experiments/langfuse_introduction
cp .env.example .env   # defaults already match the bootstrapped keys
make up                # builds the image, checks Langfuse is reachable
```

Run the stages in order:

```bash
make stage-0    # plain bot — no observability
make stage-1    # tracing
make stage-2    # sessions + users
make stage-3    # nested spans
make stage-4    # prompt management
make stage-5    # scores
make stage-7    # datasets + experiments

make ask        # non-interactive smoke turn through stage 3
make run-all    # every stage end to end, non-interactive
make down
```

Open http://localhost:3400. UI login for the bootstrapped instance is
`local@example.com` / `localpassword`.

## Next

For the theory behind each Langfuse feature and the exact trace/span data shape,
read [Langfuse features and trace structure](docs/langfuse_features.md).

Now that these concepts are familiar, see
[`langfuse_openai_agents`](../langfuse_openai_agents/README.md): it runs the
same agent as experiments 5–7 and is directly comparable.

