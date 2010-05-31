VERSION = $(shell tr -d '\n' < ../VERSION)
TARBALL = Spark-$(VERSION).tar.gz
TARBALLPATH = ../linux/dist/$(TARBALL)

all: pkg

$(TARBALL):
	cd ../linux && make tarball
	cp "$(TARBALLPATH)" "$(TARBALL)"

PKGBUILD: Makefile $(TARBALL)
	./updatepkg.sh $(VERSION)

pkg: PKGBUILD
	makepkg -f

upload: PKGBUILD $(TARBALL)
	lftp -c 'open pasaulais@pasaulais.free.fr; cd spark; put PKGBUILD; put spark.install; cd src; put $(TARBALL)'

clean: 
	rm -Rf src pkg "$(TARBALL)"
