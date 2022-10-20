"""macOS specific utilities used by Textinator"""

import platform
from typing import Tuple

import objc
from Foundation import NSBundle, NSDesktopDirectory, NSFileManager, NSUserDomainMask

__all__ = ["get_app_path", "get_mac_os_version", "verify_desktop_access"]


def verify_desktop_access():
    """Verify that the app has access to the user's Desktop

    If the App has NSDesktopFolderUsageDescription set in Info.plist,
    user will be prompted to grant Desktop access the first time this is run.

    Returns: True if access is granted, False otherwise.
    """
    with objc.autorelease_pool():
        (
            desktop_url,
            error,
        ) = NSFileManager.defaultManager().URLForDirectory_inDomain_appropriateForURL_create_error_(
            NSDesktopDirectory, NSUserDomainMask, None, False, None
        )
        if error:
            return False
        (
            desktop_files,
            error,
        ) = NSFileManager.defaultManager().contentsOfDirectoryAtURL_includingPropertiesForKeys_options_error_(
            desktop_url, [], 0, None
        )
        return not error


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
