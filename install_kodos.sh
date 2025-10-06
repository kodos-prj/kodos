#!/bin/bash

echo "Installing required packages"
pacman -S git uv whois --noconfirm

echo "Cloning kodos repo"
git clone https://github.com/kodos-prj/kodos

echo "Installing Kodos using example/testvm"
cd kodos
uv run kod -v install -c example/testvm

echo "Done"
