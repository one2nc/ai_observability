# Bifrost AI Gateway

Bifrost runs as an OpenAI-compatible AI gateway between experiment apps and upstream model providers.

## Usage

```bash
cd infra
cp .enc.example .enc
```

Set:

```text
gateway: true
bifrost_provider: openai
bifrost_api_key: sk-...
```

Then run `make up`.

The provider config is generated into `infra/bifrost/data/config.json`. The API token is not written to that file; it is referenced as `env.BIFROST_API_KEY`.

Bifrost runs with a local SQLite `config_store` because v1.5.7 requires a config store for governance routes during server bootstrap. The startup script treats `.enc` as the source of truth: when generated config changes, it backs up the old `data/config.db` and lets Bifrost bootstrap a fresh one.

## Virtual Key

After Bifrost starts, open http://localhost:8000.

1. Go to **Virtual Keys**.
2. Create a new virtual key.
3. Select the provider configured in `.enc`, for example `openai`.
4. Allow the models your experiments will call, for example `openai/gpt-4o-mini` and `openai/text-embedding-3-small`.
5. Copy the generated virtual key.

Use that key as `CHAT_API_KEY` and `EMBED_API_KEY` in experiment `.env` files.

## App Env

Point experiment LLM calls at Bifrost:

```bash
CHAT_API_KEY=<bifrost-virtual-key>
CHAT_BASE_URL=http://host.docker.internal:8000/v1
CHAT_MODEL=openai/gpt-4o-mini
```

For embeddings through Bifrost:

```bash
EMBED_API_KEY=<bifrost-virtual-key>
EMBED_BASE_URL=http://host.docker.internal:8000/v1
EMBED_MODEL=openai/text-embedding-3-small
```

Use provider-prefixed model names: `<provider>/<model>`.

## Telemetry

Bifrost is configured with its OTel plugin. It sends GenAI spans and pushed metrics to the shared OTel gateway at `http://host.docker.internal:4418`.
