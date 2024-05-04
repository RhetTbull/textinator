"""Display a window with text detection contents before copying to clipboard"""

from __future__ import annotations

from typing import TYPE_CHECKING

import AppKit
import objc
from AppKit import NSObject, NSWindow
from Foundation import NSLog
from objc import python_method

import appkitgui as gui
from pasteboard import Pasteboard

if TYPE_CHECKING:
    from textinator import Textinator

# constants
EDGE_INSET = 20
EDGE_INSETS = (EDGE_INSET, EDGE_INSET, EDGE_INSET, EDGE_INSET)
PADDING = 8
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 600


class ConfirmationWindow(NSObject):
    """Confirmation Window to confirm text before copying to clipboard"""

    def init(self):
        """Initialize the ConfirmationWindow"""
        self = objc.super(ConfirmationWindow, self).init()
        if self is None:
            return None
        return self

    @python_method
    def create_window(self) -> NSWindow:
        """Create the NSWindow object"""
        # use @python_method decorator to tell objc this is called using python
        # conventions, not objc conventions
        self.window = gui.window(
            "Textinator",
            (WINDOW_WIDTH, WINDOW_HEIGHT),
            mask=AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
        )
        self.main_view = gui.main_view(
            self.window, padding=PADDING, edge_inset=EDGE_INSETS
        )

        self.text_view = gui.text_view(
            size=(WINDOW_WIDTH - 2 * EDGE_INSET, WINDOW_HEIGHT - 50)
        )
        self.main_view.append(self.text_view)
        gui.constrain_to_parent_width(self.text_view, edge_inset=EDGE_INSET)
        self.hstack = gui.hstack(align=AppKit.NSLayoutAttributeCenterY)
        self.main_view.append(self.hstack)
        self.button_cancel = gui.button("Cancel", self, self.buttonCancel_)
        self.button_copy = gui.button(
            "Copy to clipboard", self, self.buttonCopyToClipboard_
        )
        self.button_copy.setKeyEquivalent_("\r")  # Return key
        self.button_copy.setKeyEquivalentModifierMask_(0)  # No modifier keys
        self.hstack.extend([self.button_cancel, self.button_copy])
        gui.constrain_trailing_anchor_to_parent(self.hstack, edge_inset=EDGE_INSET)

    @python_method
    def show(self, text: str, app: Textinator):
        """Create and show the window"""

        if not hasattr(self, "window"):
            self.create_window()

        self.app = app
        self.log = app.log

        with objc.autorelease_pool():
            self.log(f"Showing confirmation window with text: {text}")
            self.text_view.setString_(text)
            self.window.makeKeyAndOrderFront_(None)
            self.window.setIsVisible_(True)
            self.window.setLevel_(AppKit.NSFloatingWindowLevel + 1)
            self.window.setReleasedWhenClosed_(False)
            self.window.makeFirstResponder_(self.button_copy)
            return self.window

    def buttonCancel_(self, sender):
        """Cancel button action"""
        self.log("Cancel button clicked, closing window without copying text")
        self.window.close()

    def buttonCopyToClipboard_(self, sender):
        """Copy to clipboard button action"""
        text = self.text_view.string()
        self.log(f"Text to copy: {text}")
        if self.app.append.state:
            clipboard_text = (
                self.app.pasteboard.paste() if self.app.pasteboard.has_text() else ""
            )
            clipboard_text = f"{clipboard_text}\n{text}" if clipboard_text else text
        else:
            clipboard_text = text
        self.log(f"Setting clipboard text to: {clipboard_text}")
        self.app.pasteboard.copy(clipboard_text)
        self.window.close()
