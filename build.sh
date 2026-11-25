#!/bin/sh
# Regenerate everything from src/. Needs: pip install -r requirements.txt
set -e
cd "$(dirname "$0")/src"
python3 route.py   # route the board -> build/routed.pkl
python3 fab.py     # DRC, Gerbers, drill files, BOM, docs/pcb-preview.png
python3 kicad.py   # kicad/pw-deck.kicad_pcb for KiCad DRC
python3 stl.py     # printable parts, clash checks, docs/case-preview.png
