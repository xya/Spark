#!/bin/sh
VERSION="$1"
CHECKSUMS=$(makepkg -g 2>/dev/null | grep md5sums)
sed -i "s/pkgver=.*/pkgver=$VERSION/" PKGBUILD
sed -i "s/md5sums=(.*)/$CHECKSUMS/" PKGBUILD
