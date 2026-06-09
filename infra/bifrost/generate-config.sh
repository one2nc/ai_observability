#!/usr/bin/env sh
set -eu

if [ -z "${BIFROST_PROVIDER:-}" ]; then
  echo "BIFROST_PROVIDER is required, for example: openai, anthropic, openrouter, groq" >&2
  exit 1
fi

case "$BIFROST_PROVIDER" in
  *[!A-Za-z0-9_-]*)
    echo "BIFROST_PROVIDER may only contain letters, numbers, underscore, and hyphen" >&2
    exit 1
    ;;
esac

mkdir -p data

if [ ! -f data/encryption_key ]; then
  openssl rand -hex 32 > data/encryption_key
  chmod 600 data/encryption_key
fi

OTLP_ENDPOINT="${OTEL_EXPORTER_OTLP_ENDPOINT:-http://host.docker.internal:4418}"
OTLP_ENDPOINT="${OTLP_ENDPOINT%/}"
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-$OTLP_ENDPOINT/v1/traces}"
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="${OTEL_EXPORTER_OTLP_METRICS_ENDPOINT:-$OTLP_ENDPOINT/v1/metrics}"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT

cat > data/config.json <<EOF
{
  "\$schema": "https://www.getbifrost.ai/schema",
  "encryption_key": "env.BIFROST_ENCRYPTION_KEY",
  "client": {
    "drop_excess_requests": false,
    "enable_logging": true,
    "enforce_auth_on_inference": false
  },
  "governance": {
    "auth_config": {
      "is_enabled": false,
      "disable_auth_on_inference": true
    }
  },
  "providers": {
    "$BIFROST_PROVIDER": {
      "keys": [
        {
          "name": "$BIFROST_PROVIDER-primary",
          "value": "env.BIFROST_API_KEY",
          "models": ["*"],
          "weight": 1.0
        }
      ]
    }
  },
  "plugins": [
    {
      "enabled": true,
      "name": "otel",
      "config": {
        "service_name": "ai-obs-bifrost-gateway",
        "collector_url": "env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "trace_type": "genai_extension",
        "protocol": "http",
        "metrics_enabled": true,
        "metrics_endpoint": "env.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "metrics_push_interval": 15,
        "plugin_span_filter": {
          "mode": "exclude",
          "plugins": ["telemetry", "logging", "governance", "otel", "compat"]
        }
      }
    }
  ],
  "config_store": {
    "enabled": true,
    "type": "sqlite",
    "config": {
      "path": "./config.db"
    }
  },
  "logs_store": {
    "enabled": true,
    "type": "sqlite",
    "config": {
      "path": "./logs.db"
    }
  }
}
EOF

chmod 600 data/config.json
echo "Generated data/config.json for Bifrost provider: $BIFROST_PROVIDER"
