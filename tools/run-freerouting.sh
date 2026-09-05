#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
java_bin="${FREEROUTING_JAVA:-/usr/lib/jvm/java-25-openjdk-amd64/bin/java}"

if [[ ! -x "$java_bin" ]]; then
  echo "Freerouting 2.4.1 needs Java 25: $java_bin" >&2
  exit 1
fi

exec "$java_bin" -jar "${script_dir}/freerouting.jar" \
  -dct 0 \
  --profile.email=disabled@localhost.invalid \
  --profile.allow_telemetry=false \
  --profile.allow_contact=false \
  --usage_and_diagnostic_data.disable_analytics=true \
  "$@"
