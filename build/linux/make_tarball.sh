#!/bin/sh
SPARK_ROOT="$1"
for file in setup.py MANIFEST.in; do
    if [ ! -e "$SPARK_ROOT/$file" ]; then
        cp "$SPARK_ROOT/build/linux/$file" "$SPARK_ROOT/$file"
    fi
done

cd "$SPARK_ROOT"
python setup.py sdist
cp "$SPARK_ROOT/dist"/* "$SPARK_ROOT/build/linux"
rm -Rf "$SPARK_ROOT/dist"

for file in setup.py MANIFEST.in MANIFEST; do
    if [ -e "$SPARK_ROOT/$file" ]; then
        rm "$SPARK_ROOT/$file"
    fi
done
