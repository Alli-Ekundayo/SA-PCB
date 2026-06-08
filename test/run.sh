#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

python3 -m py_compile src/py_utils/multistart.py src/py_utils/run_with_config.py test/benchmark.py test/rtree_parity.py
python3 src/py_utils/multistart.py --help >/dev/null
python3 src/py_utils/run_with_config.py --config test/simple.json --print-effective >/dev/null
rm -rf cache

echo "Python multistart/config smoke tests passed."
