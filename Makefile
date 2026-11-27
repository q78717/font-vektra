# Follows the googlefonts-project-template Makefile. Vektra's source is generated
# by sources/build_vektra.py, so `make build` runs sources/build.sh, which writes the
# UFO and then runs gftools builder on sources/config.yaml.
FAMILY=Vektra
SOURCES=sources/build_vektra.py sources/build_specimen.py sources/specimen_template.html sources/tools/check_font.py $(wildcard sources/config*.yaml)

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

build: build.stamp

venv: venv/touchfile

build.stamp: venv $(SOURCES)
	rm -rf fonts
	./sources/build.sh && touch build.stamp

venv/touchfile: requirements.txt
	test -d venv || python3 -m venv venv
	./venv/bin/pip install -Ur requirements.txt
	touch venv/touchfile

test: build.stamp
	which fontspector || (echo "fontspector not found. Please install it with 'cargo binstall fontspector'." && exit 1)
	mkdir -p out/ out/fontspector
	fontspector --profile googlefonts -l warn --full-lists --succinct --html out/fontspector/fontspector-report.html --ghmarkdown out/fontspector/fontspector-report.md --badges out/badges fonts/ttf/Vektra-Regular.ttf || echo '::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in Vektra. Please check the generated report.'

qa: build.stamp
	test -d venv-test || (python3 -m venv venv-test && ./venv-test/bin/pip install -Ur requirements-qa.txt)
	./venv-test/bin/fontbakery check-googlefonts fonts/ttf/Vektra-Regular.ttf
	./venv-test/bin/fontbakery check-universal fonts/ttf/Vektra-Regular.ttf

proof: venv build.stamp
	which diff3proof || (echo "diff3proof not found. Please install it with 'cargo binstall diffenator3'." && exit 1)
	mkdir -p out/ out/proof; for f in fonts/ttf/*.ttf; do diff3proof $$f --output out/proof/$$(basename $$f .ttf); done

images: venv build.stamp
	./venv/bin/python3 sources/tools/readme_images.py

clean:
	rm -rf venv build.stamp out
	find . -name "*.pyc" -delete

update: venv
	venv/bin/pip install --upgrade pip-tools
	# See https://pip-tools.readthedocs.io/en/latest/#a-note-on-resolvers for
	# the `--resolver` flag below.
	venv/bin/pip-compile --upgrade --verbose --resolver=backtracking requirements.in
	venv/bin/pip-sync requirements.txt

	git commit -m "Update requirements" requirements.txt
	git push

.PHONY: help build venv test qa proof images clean update
