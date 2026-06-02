#!/bin/bash
# Instala dependências na pasta layer/ para deploy como Lambda Layer
set -e

rm -rf layer/python
mkdir -p layer/python

pip install \
  --target layer/python \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.13 \
  --only-binary=:all: \
  -r lambda/requirements.txt

echo "Layer instalada em layer/python"
echo "Tamanho: $(du -sh layer/python | cut -f1)"
