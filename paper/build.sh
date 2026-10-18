#!/usr/bin/env bash
# Build paper/ai-disclosure-trend-audit.pdf from paper/paper.md.
# The TeX Live in the build environment lacks lmodern.sty, so the generated
# source drops that one line and sets fonts through fontspec instead.
set -euo pipefail
cd "$(dirname "$0")"
pandoc paper.md -s -o paper.tex --pdf-engine=xelatex \
  -V mainfont="Bitstream Charter" -V sansfont="DejaVu Sans" -V monofont="DejaVu Sans Mono" \
  -V fontsize=11pt
sed -i 's/^\\usepackage{lmodern}$/% lmodern not installed; fonts set by fontspec/' paper.tex
xelatex -interaction=nonstopmode -halt-on-error paper.tex >/dev/null
xelatex -interaction=nonstopmode -halt-on-error paper.tex >/dev/null
mv paper.pdf ai-disclosure-trend-audit.pdf
rm -f paper.aux paper.log paper.out paper.tex
pdfinfo ai-disclosure-trend-audit.pdf | grep Pages
