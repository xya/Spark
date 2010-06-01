VERSION = $(shell tr -d '\n' < ../VERSION)
TARBALL = dist/Spark-$(VERSION).tar.gz

all: tarball
	
$(TARBALL): Makefile setup.py
	[ -L src ] || ln -s ../../src src
	[ -L icons ] || ln -s ../../icons icons
	[ -f COPYING ] || cp ../../COPYING .
	[ -f NEWS ] || cp ../../NEWS .
	sed -i "s/version='.*'/version='$(VERSION)'/" setup.py
	python setup.py sdist

tarball: $(TARBALL)

upload: $(TARBALL)
	lftp -c 'open pasaulais@pasaulais.free.fr; cd spark/src; put $(TARBALL)'

clean: 
	rm -Rf dist src icons MANIFEST COPYING NEWS
