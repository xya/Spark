VERSION = $(shell tr -d '\n' < ../VERSION)
TARBALL = spark_$(VERSION).orig.tar.gz
TARBALLPATH = ../linux/dist/Spark-$(VERSION).tar.gz
DEBMETADATA = debian/rules debian/changelog debian/compat debian/control \
  debian/copyright debian/pyversions

all: deb

$(TARBALL): clean-tarball-dir
	cd ../linux && make tarball
	cp "$(TARBALLPATH)" "$(TARBALL)"

prepare: $(TARBALL) $(DEBMETADATA)
	tar xfz $(TARBALL)
	mv Spark-$(VERSION) spark-$(VERSION)
	cp -R debian spark-$(VERSION)

deb: prepare
	cd spark-$(VERSION) && debuild

deb-src: prepare
	cd spark-$(VERSION) && debuild -S

upload: deb-src
	dput ppa:pasaulais/spark $(shell ls spark_$(VERSION)-*.changes | sort -r | head -1)

clean-tarball-dir:
	rm -Rf spark-$(VERSION)

clean: clean-tarball-dir
	rm -Rf "$(TARBALL)" spark_*.dsc spark_*.build spark_*.changes spark_*.diff.gz spark_*.deb
