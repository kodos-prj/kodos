#!/bin/bash

echo "Installing required packages"
pacman -Syy
pacman -S git uv --noconfirm

echo "Installing pith binary"
curl -L -o /usr/local/bin/pith \
    https://github.com/kodos-prj/pistacho/releases/latest/download/pith-v0.4.3-linux-amd64
chmod +x /usr/local/bin/pith

echo "Cloning kodos repo"
git clone https://github.com/kodos-prj/kodos

echo "Installing Kodos using example/testvm"
cd kodos
uv run kod -v install -c example/testvm

echo "Done"
