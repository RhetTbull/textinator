"""Utilities for working with System Preferences > Users & Groups > Login Items on macOS."""

from typing import List

import applescript

__all__ = ["add_login_item", "list_login_items", "remove_login_item"]

# The following functions are used to manipulate the Login Items list in System Preferences
# To use these, your app must include the com.apple.security.automation.apple-events entitlement
# in its entitlements file during signing and must have the NSAppleEventsUsageDescription key in
# its Info.plist file
# These functions use AppleScript to interact with System Preferences. I know of no other way to
# do this programmatically from Python.  If you know of a better way, please let me know!


def add_login_item(app_name: str, app_path: str, hidden: bool = False):
    """Add app to login items"""
    scpt = (
        'tell application "System Events" to make login item at end with properties '
        + f'{{name:"{app_name}", path:"{app_path}", hidden:{"true" if hidden else "false"}}}'
    )
    applescript.AppleScript(scpt).run()


def remove_login_item(app_name: str):
    """Remove app from login items"""
    scpt = f'tell application "System Events" to delete login item "{app_name}"'
    applescript.AppleScript(scpt).run()


def list_login_items() -> List[str]:
    """Return list of login items"""
    scpt = 'tell application "System Events" to get the name of every login item'
    return applescript.AppleScript(scpt).run()
