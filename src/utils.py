"""macOS specific utilities used by Textinator"""

import os
import platform
from typing import Tuple

import objc
from Foundation import (
    NSURL,
    NSBundle,
    NSDesktopDirectory,
    NSFileManager,
    NSLog,
    NSUserDefaults,
    NSUserDomainMask,
)

__all__ = [
    "get_app_path",
    "get_mac_os_version",
    "get_screenshot_location",
    "verify_directory_access",
    "verify_screenshot_access",
]


def verify_directory_access(path: str) -> str | None:
    """Verify that the app has access to the specified directory

    Args:
        path: str path to the directory to verify access to.

    Returns: path if access is verified, None otherwise.
    """
    with objc.autorelease_pool():
        path_url = NSURL.fileURLWithPath_(path)
        (
            directory_files,
            error,
        ) = NSFileManager.defaultManager().contentsOfDirectoryAtURL_includingPropertiesForKeys_options_error_(
            path_url, [], 0, None
        )
        if error:
            NSLog(f"verify_directory_access: {error.localizedDescription()}")
            return None
        return path


def get_screenshot_location() -> str:
    """Return path to the default location for screenshots

    First checks the custom screenshot location from com.apple.screencapture.
    If not set or inaccessible, assumes Desktop.

    If the App has NSDesktopFolderUsageDescription set in Info.plist,
    user will be prompted to grant Desktop access the first time this is run
    if the screenshot location is the Desktop.

    Returns: str path to the screenshot location.
    """
    with objc.autorelease_pool():
        # Check for custom screenshot location
        screencapture_defaults = NSUserDefaults.alloc().initWithSuiteName_(
            "com.apple.screencapture"
        )
        if custom_location := screencapture_defaults.stringForKey_("location"):
            return os.path.expanduser(custom_location)

        # Fallback to Desktop if no custom location or if it's inaccessible
        (
            desktop_url,
            error,
        ) = NSFileManager.defaultManager().URLForDirectory_inDomain_appropriateForURL_create_error_(
            NSDesktopDirectory, NSUserDomainMask, None, False, None
        )
        return str(desktop_url.path()) if not error else os.path.expanduser("~/Desktop")


def verify_screenshot_access() -> str | None:
    """Verify that the app has access to the user's screenshot location or Desktop

    First checks the custom screenshot location from com.apple.screencapture.
    If not set or inaccessible, checks the Desktop.

    If the App has NSDesktopFolderUsageDescription set in Info.plist,
    user will be prompted to grant Desktop access the first time this is run.

    Returns: path to screenshot location if access otherwise None
    """
    with objc.autorelease_pool():
        screenshot_location = get_screenshot_location()
        return verify_directory_access(screenshot_location)


def get_mac_os_version() -> Tuple[str, str, str]:
    """Returns tuple of str in form (version, major, minor) containing OS version, e.g. 10.13.6 = ("10", "13", "6")"""
    version = platform.mac_ver()[0].split(".")
    if len(version) == 2:
        (ver, major) = version
        minor = "0"
    elif len(version) == 3:
        (ver, major, minor) = version
    else:
        raise (
            ValueError(
                f"Could not parse version string: {platform.mac_ver()} {version}"
            )
        )

    # python might return 10.16 instead of 11.0 for Big Sur and above
    if ver == "10" and int(major) >= 16:
        ver = str(11 + int(major) - 16)
        major = minor
        minor = "0"

    return (ver, major, minor)


def get_app_path() -> str:
    """Return path to the bundle containing this script"""
    # Note: This must be called from an app bundle built with py2app or you'll get
    # the path of the python interpreter instead of the actual app
    return NSBundle.mainBundle().bundlePath()
