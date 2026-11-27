# Follows the googlefonts-project-template Makefile. Vektra's source is generated
# by sources/build_vektra.py, so `make build` runs sources/build.sh, which writes the
# UFO and then runs gftools builder on sources/config.yaml.
#
# build, test, qa, proof, images and update are shared by every rv font repo: they
# come from font-tools (https://github.com/q78717/font-tools), whose `rvfont makefile`
# writes them to .rvfont.mk from the version pinned in requirements.txt.
FAMILY = Vektra
SOURCES = sources/build_vektra.py sources/build_specimen.py sources/specimen_template.html $(wildcard sources/config*.yaml)
GF_FONTS = fonts/ttf/Vektra-Regular.ttf
UNIVERSAL_FONTS = 

# One build venv shared by all the font repos: ../.venv-fonts when it exists, else
# ./venv (what CI uses). Same for the FontBakery venv: ../.venv-fonts-qa or ./venv-test.
FONT_VENV ?= $(if $(wildcard ../.venv-fonts/bin/python),../.venv-fonts,venv)
FONT_QA_VENV ?= $(if $(wildcard ../.venv-fonts-qa/bin/python),../.venv-fonts-qa,venv-test)
override FONT_VENV := $(abspath $(FONT_VENV))
override FONT_QA_VENV := $(abspath $(FONT_QA_VENV))

help:
	@echo "###"
	@echo "# Build targets for $(FAMILY)"
	@echo "###"
	@echo
	@echo "  make build:  Builds the fonts and places them in the fonts/ directory"
	@echo "  make test:   Tests the fonts with fontspector"
	@echo "  make qa:     Tests the fonts with FontBakery (googlefonts + universal)"
	@echo "  make proof:  Creates HTML proof documents in the out/proof/ directory"
	@echo "  make images: Creates PNG specimen images in the documentation/ directory"
	@echo
	@echo "  venv: $(FONT_VENV)"
	@echo

venv: $(FONT_VENV)/touchfile

$(FONT_VENV)/touchfile: requirements.txt
	test -d $(FONT_VENV) || python3 -m venv $(FONT_VENV)
	$(FONT_VENV)/bin/pip install -Ur requirements.txt
	touch $@

.rvfont.mk: $(FONT_VENV)/touchfile
	$(FONT_VENV)/bin/rvfont makefile > $@

clean:
	rm -rf venv build.stamp out .rvfont.mk
	find . -name "*.pyc" -not -path "*/venv*" -delete

ifneq ($(filter-out help venv clean,$(MAKECMDGOALS)),)
include .rvfont.mk
endif

.PHONY: help venv clean
