#!/usr/bin/env sh

set -e

TMP=$(mktemp -d -t prusalibUpdate_XXXXXX)

git clone git@github.com:prusa3d/PrusaKicadLib.git $TMP

mkdir -p prusaman/resources/prusalib.pretty
rm -rf prusaman/resources/prusalib.pretty/*

FLIB=${TMP}/prusa-footprints/

cp ${FLIB}/prusa_other.pretty/hole4cutter-2mm.kicad_mod \
   ${FLIB}/prusa_other.pretty/hole4cutter-1,5mm.kicad_mod \
        prusaman/resources/prusalib.pretty

rm -rf ${TMP}
