# Observability and OpenTelemetry

This project can run without an OpenTelemetry (OTEL) backend or collector. By default most SDKs will drop data or no‑op if no exporter is configured. You might see non‑fatal warnings about failed exports, but the app should run normally.

## Running Without a Backend
- Safe by default: telemetry is dropped; app logic continues.
- If warnings are noisy, disable the SDK or exporters (below).

## Disable Completely
- PowerShell: `$env:OTEL_SDK_DISABLED = "true"`
- Bash: `export OTEL_SDK_DISABLED=true`

## Disable Only the Exporters
- PowerShell: `$env:OTEL_TRACES_EXPORTER = "none"; $env:OTEL_METRICS_EXPORTER = "none"; $env:OTEL_LOGS_EXPORTER = "none"`
- Bash: `export OTEL_TRACES_EXPORTER=none OTEL_METRICS_EXPORTER=none OTEL_LOGS_EXPORTER=none`

## Console Exporters (Local Debugging)
- PowerShell: `$env:OTEL_TRACES_EXPORTER = "console"; $env:OTEL_LOGS_EXPORTER = "console"; $env:OTEL_METRICS_EXPORTER = "none"`
- Bash: `export OTEL_TRACES_EXPORTER=console OTEL_LOGS_EXPORTER=console OTEL_METRICS_EXPORTER=none`

## Enabling Later (Collector or Backend)
- Set endpoint only:
  - gRPC (4317):
    - PowerShell: `$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"`
    - Bash: `export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`
  - HTTP (4318):
    - PowerShell: `$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318"`
    - Bash: `export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`
- Optional protocol hints:
  - gRPC: `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`
  - HTTP/protobuf: `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`

## Edge Cases
- If your app initializes an exporter eagerly and fails hard when unreachable, either:
  - Guard init with retries/fallback, or
  - Use `OTEL_SDK_DISABLED=true` (development), or set exporters to `none`.

## Tips
- Scope: these environment variables affect the current shell session. Put them in your shell profile or project startup scripts if you need them every run.
- Virtualenv: you can optionally add them to your Python venv activation scripts (e.g., `venv/Scripts/Activate.ps1`) so they apply whenever the venv is activated.

## Virtualenv Activation Defaults
The venv activation script sets safe OpenTelemetry defaults each time you activate the environment. Control behavior with `MUTT_OTEL_MODE`:

- `disabled` (default): sets `OTEL_SDK_DISABLED=true` and exporters to `none` unless already set.
- `console`: enables console exporters for traces and logs (`OTEL_TRACES_EXPORTER=console`, `OTEL_LOGS_EXPORTER=console`), metrics exporter defaults to `none` unless set.
- any other value: leaves existing OTEL variables unchanged.

Examples (PowerShell):
- Console mode for this session: `$env:MUTT_OTEL_MODE = "console"; .\venv\Scripts\Activate.ps1`
- Back to disabled: `$env:MUTT_OTEL_MODE = "disabled"; .\venv\Scripts\Activate.ps1`
- Use custom OTEL settings: `Remove-Item Env:MUTT_OTEL_MODE -ErrorAction SilentlyContinue; .\venv\Scripts\Activate.ps1`
