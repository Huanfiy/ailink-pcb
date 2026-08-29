#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

exec java -jar "${script_dir}/freerouting.jar" \
  -dct 0 \
  --profile.email=disabled@localhost.invalid \
  --profile.allow_telemetry=false \
  --profile.allow_contact=false \
  --usage_and_diagnostic_data.disable_analytics=true \
  "$@"
