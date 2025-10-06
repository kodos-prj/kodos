#!/bin/bash

echo "Update mirrorlist"
curl 'https://archlinux.org/mirrorlist/?country=CA&protocol=http&protocol=https&ip_version=4' -o /etc/pacman.d/mirrorlist
