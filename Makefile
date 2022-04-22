
.SHELLFLAGS += -e

PCM_RESOURCES := $(shell find pcm -type f -print)

.PHONY: package pcm

all: pcm

package:
	# Clean up any python cache
	python3 -Bc "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')]"
	python3 -Bc "import pathlib; [p.rmdir() for p in pathlib.Path('.').rglob('__pycache__')]"
	rm -rf dist/* build/lib/*
	# A hack follows - bdist_wheel doesn't exclude files
	mv prusaman/resources/prusalib/prusa-3dmodels /tmp/models || true
	python3 setup.py sdist bdist_wheel
	mv /tmp/models prusaman/resources/prusalib/prusa-3dmodels || true

pcm: build/pcm.zip

build/pcm.zip: package $(PCM_RESOURCES)
	rm -rf build/pcm build/prusaman.zip
	mkdir -p build/pcm

	cp -r pcm/* build/pcm
	cp dist/*.whl build/pcm/plugins
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

clean:
	rm -rf dist build
