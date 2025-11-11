#!/usr/bin/env bash
set -euo pipefail

# Simple snmptrapd traphandle script to forward traps to MUTT Ingestor via HTTP.
# Requires environment variables:
#   MUTT_INGEST_URL      e.g., https://ingestor.lab:8443/ingest or http://127.0.0.1:8080/ingest
#   MUTT_INGEST_API_KEY  API key for X-API-KEY header
#   MUTT_CACERT          Optional path to custom CA PEM for HTTPS verification

MUTT_URL="${MUTT_INGEST_URL:-http://127.0.0.1:8080/ingest}"
API_KEY="${MUTT_INGEST_API_KEY:?Set MUTT_INGEST_API_KEY in environment}"

payload="$(cat)"

hostname=$(hostname -f 2>/dev/null || hostname)
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Try to extract trap OID from input (supports -On/-n output forms)
trap_oid=$(echo "$payload" | awk '/SNMPv2-MIB::snmpTrapOID\.0|1\.3\.6\.1\.6\.3\.1\.1\.4\.1\.0/ {print $NF; exit}')

# JSON-escape payload
escaped=$(printf '%s' "$payload" | tr -d '\r' | sed 's/\\/\\\\/g; s/"/\\"/g')

if [[ -n "${trap_oid:-}" ]]; then
  json=$(printf '{"hostname":"%s","timestamp":"%s","message":"%s","trap_oid":"%s"}' \
    "$hostname" "$timestamp" "$escaped" "$trap_oid")
else
  json=$(printf '{"hostname":"%s","timestamp":"%s","message":"%s"}' \
    "$hostname" "$timestamp" "$escaped")
fi

curl_opts=( -sS -X POST )
if [[ -n "${MUTT_CACERT:-}" ]]; then
  curl_opts+=( --cacert "$MUTT_CACERT" )
fi

curl "${curl_opts[@]}" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  --data "$json" \
  "$MUTT_URL" >/dev/null
