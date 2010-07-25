#!/bin/sh
if [ $# = 0 ]; then
    VERSION=$(tr -d '\n' < ../VERSION)
else
    VERSION="$1"
fi
CHECKSUMS=$(makepkg -g 2>/dev/null | grep md5sums)
sed -i "s/pkgver=.*/pkgver=$VERSION/" PKGBUILD
sed -i "s/md5sums=(.*)/$CHECKSUMS/" PKGBUILD
