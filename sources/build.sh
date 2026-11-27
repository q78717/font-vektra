#!/usr/bin/env bash
# Build Vektra in one command:  sources/build.sh
#   1. sources/build_vektra.py draws every glyph and writes the UFO source
#   2. gftools builder compiles, hints and checks it into fonts/ttf and fonts/webfonts
#   3. a STAT table is added, the specimen page is rebuilt, and the font is smoke-tested
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d "venv/bin" ]; then
  export PATH="$PWD/venv/bin:$PATH"
fi
python3 sources/build_vektra.py --ufo sources/ufo
(cd sources && gftools builder config.yaml)
python3 sources/tools/add_stat.py fonts/ttf fonts/webfonts
python3 sources/build_specimen.py --fonts fonts/webfonts --ttf fonts/ttf --out documentation/specimen/index.html
python3 sources/tools/check_font.py fonts/ttf/Vektra-Regular.ttf
