#!/usr/bin/env bash
# Build Vektra in one command:  sources/build.sh
#   1. sources/build_vektra.py draws every glyph and writes the UFO source
#   2. gftools builder compiles, hints and checks it into fonts/ttf and fonts/webfonts
#   3. a STAT table is added, the specimen page is rebuilt, and the font is smoke-tested
set -euo pipefail
cd "$(dirname "$0")/.."
# Build venv: $FONT_VENV (set by make), else the shared ../.venv-fonts, else ./venv.
for v in "${FONT_VENV:-}" "$PWD/../.venv-fonts" "$PWD/venv"; do
  if [ -n "$v" ] && [ -x "$v/bin/python3" ]; then export PATH="$v/bin:$PATH"; break; fi
done
python3 sources/build_vektra.py --ufo sources/ufo
(cd sources && gftools builder config.yaml)
python3 sources/tools/add_stat.py fonts/ttf fonts/webfonts
python3 sources/build_specimen.py --fonts fonts/webfonts --ttf fonts/ttf --out documentation/specimen/index.html
font-tools check-font fonts/ttf/Vektra-Regular.ttf --glyphset GF_Latin_Core
