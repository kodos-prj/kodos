#!/bin/bash

echo "Installing required packages"
pacman -Syy
pacman -S git uv whois --noconfirm

echo "Update mirrorlist"
curl 'https://archlinux.org/mirrorlist/?country=CA&protocol=http&protocol=https&ip_version=4' -o /etc/pacman.d/mirrorlist

echo "Cloning kodos repo"
git clone https://github.com/kodos-prj/kodos

echo "Installing Kodos using example/testvm"
cd kodos
uv run kod -v install -c example/testvm

echo "Done"
