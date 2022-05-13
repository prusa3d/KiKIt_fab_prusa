
.SHELLFLAGS += -e

PCM_RESOURCES := $(shell find pcm -type f -print)
KIKIT_URL ?= "https://github.com/yaqwsx/KiKit.git"

.PHONY: package pcm

all: pcm

package:
	# Clean up any python cache
	python3 -Bc "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')]"
	python3 -Bc "import pathlib; [p.rmdir() for p in pathlib.Path('.').rglob('__pycache__')]"

	# Remove all prints in iBom version
	releng/bakeIbomVersion.py prusaman/resources/ibom/InteractiveHtmlBom/version.py | sponge prusaman/resources/ibom/InteractiveHtmlBom/version.py

	rm -rf dist/* build/lib/*
	python3 setup.py sdist bdist_wheel

	git submodule foreach git reset --hard

pcm: build/pcm.zip

build/kikit-src:
	git clone $(KIKIT_URL) $@

build/pcm.zip: package $(PCM_RESOURCES) build/kikit-src
	rm -rf build/pcm build/prusaman.zip
	mkdir -p build/pcm

	cp -r pcm/* build/pcm

	# Copy prusaman package
	cp dist/*.whl build/pcm/plugins
	# Update and copy kikit package
	cd build/kikit-src && git pull && make package
	cp build/kikit-src/dist/*.whl build/pcm/plugins

	find build/pcm -name "*.pyc" -type f -delete
	# Read version from git
	releng/setJson.py \
		-s versions.-1.version=\"$$(git describe --tags --abbrev=0 | cut -c 2-)\" \
		build/pcm/metadata.json build/pcm/metadata.json
	releng/setJson.py \
	 	-s versions.-1.install_size=$$( find build/pcm -type f -exec ls -la {} + | tr -s ' ' | cut -f5 -d' ' | paste -s -d+ - | bc ) \
		build/pcm/metadata.json build/pcm/metadata.json

	cd build/pcm && zip ../prusaman.zip -r *
	cp build/pcm/metadata.json build/pcm-metadata.json
	releng/setJson.py \
		-s versions.-1.download_sha256=\"$$( sha256sum build/prusaman.zip | cut -d' ' -f1)\" \
		-s versions.-1.download_size=$$( du -sb build/prusaman.zip | cut -f1) \
		-s versions.-1.download_url=\"TBA\" \
		build/pcm-metadata.json build/pcm-metadata.json

test: test-system

test-system: build/test $(shell find prusaman -type f)
	cd build/test && bats ../../test/system

build/test:
	mkdir -p $@

clean:
	rm -rf dist build
