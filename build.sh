#!/bin/sh

# Build, sign and package Textinator as a DMG file for release
# this requires create-dmg: `brew install create-dmg` to install

# build with py2app
echo "Cleaning up old build files..."
test -d dist && rm -rf dist/
test -d build && rm -rf build/

echo "Running py2app"
python3 setup.py py2app

# TODO: this doesn't appear to be needed (only for sandboxed apps)
# py2app will sign the app with the ad-hoc certificate
# sign with ad-hoc certificate (if you have an Apple Developer ID, you can use your developer certificate instead)
# for the app to send AppleEvents to other apps, it needs to be signed and include the
# com.apple.security.automation.apple-events entitlement in the entitlements file
# --force: force signing even if the app is already signed
# --deep: recursively sign all embedded frameworks and plugins
# --options=runtime: Preserve the hardened runtime version
# --entitlements: use specified the entitlements file
# -s -: sign the code at the path(s) given using this identity; "-" means use the ad-hoc certificate
# echo "Signing with codesign"
# codesign \
#   --force \
#   --deep \
#   --options=runtime \
#   --preserve-metadata=identifier,entitlements,flags,runtime \
#   --entitlements=entitlements.plist \
#   -s - \
#   dist/Textinator.app

# create installer DMG
# to add a background image to the DMG, add the following to the create-dmg command:
#   --background "installer_background.png" \
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
