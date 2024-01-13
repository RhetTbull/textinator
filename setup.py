"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup

# The version number; do not change this manually! It is updated by bumpversion (https://github.com/c4urself/bump2version)
__version__ = "0.9.3"

# The file that contains the main application
APP = ["src/textinator.py"]

# Include additional python modules here; probably not the best way to do this
# but I couldn't figure out how else to get py2app to include modules in the src/ folder
DATA_FILES = [
    "src/icon.png",
    "src/icon_paused.png",
    "src/loginitems.py",
    "src/macvision.py",
    "src/pasteboard.py",
    "src/utils.py",
]

# These values will be included by py2app into the Info.plist file in the App bundle
# See https://developer.apple.com/documentation/bundleresources/information_property_list?language=objc
# for more information
PLIST = {
    # LSUIElement tells the OS that this app is a background app that doesn't appear in the Dock
    "LSUIElement": True,
    # CFBundleShortVersionString is the version number that appears in the App's About box
    "CFBundleShortVersionString": __version__,
    # CFBundleVersion is the build version (here we use the same value as the short version)
    "CFBundleVersion": __version__,
    # NSDesktopFolderUsageDescription is the message that appears when the app asks for permission to access the Desktop folder
    "NSDesktopFolderUsageDescription": "Textinator needs access to your Desktop folder to detect new screenshots. "
    "If you have changed the default location for screenshots, "
    "you will also need to grant Textinator full disk access in "
    "System Preferences > Security & Privacy > Privacy > Full Disk Access.",
    # NSAppleEventsUsageDescription is the message that appears when the app asks for permission to send Apple events
    "NSAppleEventsUsageDescription": "Textinator needs permission to send AppleScript events to add itself to Login Items.",
    # NSServices is a list of services that the app provides that will appear in the Services menu
    # For more information on NSServices, see: https://developer.apple.com/documentation/bundleresources/information_property_list/nsservices?language=objc
    "NSServices": [
        {
            "NSMenuItem": {"default": "Detect Text With Textinator"},
            "NSMessage": "detectTextInImage",
            "NSPortName": "Textinator",
            "NSUserData": "detectTextInImage",
            "NSRequiredContext": {"NSTextContent": "FilePath"},
            "NSSendTypes": ["NSPasteboardTypeURL"],
            "NSSendFileTypes": ["public.image"],
        },
    ],
}

# Options for py2app
OPTIONS = {
    # The icon file to use for the app (this is App icon in Finder, not the status bar icon)
    "iconfile": "icon.icns",
    "plist": PLIST,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    name="Textinator",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
