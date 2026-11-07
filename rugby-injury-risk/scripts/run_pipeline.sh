#!/usr/bin/env bash
# Rebuild the offline pipeline from the raw lake (no network): staging -> entities -> marts -> injuries.
# Usage: scripts/run_pipeline.sh [season ...]   (default: pilot seasons 2022-2023..2024-2025)
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
export DAGSTER_HOME="${DAGSTER_HOME:-$PWD/.dagster_home}"
mkdir -p "$DAGSTER_HOME"
SEASONS=("${@:-2022-2023 2023-2024 2024-2025}")
read -r -a SEASONS <<< "${SEASONS[*]}"

materialize() {
  echo ">>> $*"
  uv run dagster asset materialize --working-directory . --module-name orchestration.definitions "$@"
}

for season in "${SEASONS[@]}"; do
  for asset in allrugby_staging_matches allrugby_staging_appearances allrugby_staging_profiles \
    calendar_staging; do
    materialize --select "$asset" --partition "$season"
  done
done
for season in "${SEASONS[@]}"; do
  materialize --select player_entities --partition "$season"
done
materialize --select participation_marts
materialize --select injury_mentions
materialize --select injury_episodes
echo "PIPELINE_OK"
