#!/usr/bin/env bash
# Runs the data-pack + workbook tests, then the full suite. Usage: ./scripts/test_data_pack.sh [path/to/incident_data_pack]
set -e; cd "$(dirname "$0")/.."; export PYTHONPATH="$PWD"
export DATA_PACK="${1:-$PWD/data/pack}"
python "$DATA_PACK/tools/validate_pack.py" "$DATA_PACK" | tail -1
pytest tests/test_data_pack.py -v
pytest -q
