#!/bin/sh

# Build, sign and package Textinator as a DMG file for release
# this requires create-dmg: `brew install create-dmg` to install

#   --background "installer_background.png" \

# build with py2app
echo "Running py2app"
test -d dist && rm -rf dist/
test -d build && rm -rf build/
python setup.py py2app

# sign with adhoc certificate
echo "Signing with codesign"
codesign --force --deep -s - dist/Textinator.app

# create installer DMG
echo "Creating DMG"
test -f Textinator-Installer.dmg && rm Textinator-Installer.dmg
create-dmg \
  --volname "Textinator Installer" \
  --volicon "icon.icns" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "Textinator.app" 200 190 \
  --hide-extension "Textinator.app" \
  --app-drop-link 600 185 \
  "Textinator-Installer.dmg" \
  "dist/"
