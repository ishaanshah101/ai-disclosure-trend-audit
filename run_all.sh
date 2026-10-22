#!/usr/bin/env bash
# Reproduce every number in the paper from the committed data.
#   ./run_all.sh                 analysis from the committed rater output
#   REBUILD_CORPUS=1 ./run_all.sh   re-enumerate EDGAR and rebuild the corpus
#                                   (about 25 minutes; needs SEC_USER_AGENT)
set -euo pipefail
cd "$(dirname "$0")"

python3 src/stats.py

if [[ "${REBUILD_CORPUS:-0}" == "1" ]]; then
  python3 src/frame.py
  python3 src/denominators.py
  python3 src/sample_filings.py
  python3 src/fetch_and_extract.py
  python3 src/term_audit.py            # candidates; verdicts are committed
  python3 src/term_audit.py --apply
  python3 src/build_rating_sets.py     # the rater passes are not re-run here
  python3 src/phrase_reuse.py
  python3 src/xbrl_size.py
fi

python3 src/validate_ratings.py
python3 src/agreement.py
python3 src/third_pass.py --merge
python3 src/build_calibration.py --score
python3 src/analyze.py
python3 src/analyze.py --unweighted   # pooled-sample comparison file
python3 src/figures.py
python3 src/revision2.py            # item tags need the downloaded 10-Ks in data/filings
python3 src/figures_rev2.py
python3 src/build_browser.py
python3 src/verify_paper.py
