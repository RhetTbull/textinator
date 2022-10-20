"""macOS Pasteboard/Clipboard access using native APIs"""

import os
import typing as t

from AppKit import NSPasteboard, NSPasteboardTypePNG, NSPasteboardTypeString
from Foundation import NSData


class Pasteboard:
    """macOS Pasteboard/Clipboard Class"""

    def __init__(self):
        self.pasteboard = NSPasteboard.generalPasteboard()
        self._change_count = self.pasteboard.changeCount()

    def copy(self, text):
        """Copy text to clipboard

        Args:
            text (str): Text to copy to clipboard
        """
        self.set_text(text)

    def paste(self):
        """Retrieve text from clipboard

        Returns: str
        """
        return self.get_text()

    def append(self, text: str):
        """Append text to clipboard

        Args:
            text (str): Text to append to clipboard
        """
        new_text = self.get_text() + text
        self.set_text(new_text)

    def clear(self):
        """Clear clipboard"""
        self.pasteboard.clearContents()
        self._change_count = self.pasteboard.changeCount()

    def copy_image(self, filename: t.Union[str, os.PathLike]):
        """Copy image to clipboard from filename

        Args:
            filename (os.PathLike): Filename of image to copy to clipboard
        """
        if not isinstance(filename, str):
            filename = str(filename)
        self.set_image(filename)

    def paste_image(self, filename: t.Union[str, os.PathLike], overwrite: bool = False):
        """Paste image from clipboard to filename in PNG format

        Args:
            filename (os.PathLike): Filename of image to paste to
            overwrite (bool): Overwrite existing file

        Raises:
            FileExistsError: If file exists and overwrite is False
        """
        if not isinstance(filename, str):
            filename = str(filename)
        self.get_image(filename, overwrite)

    def set_text(self, text: str):
        """Set text on clipboard

        Args:
            text (str): Text to set on clipboard
        """
        self.pasteboard.clearContents()
        self.pasteboard.setString_forType_(text, NSPasteboardTypeString)
        self._change_count = self.pasteboard.changeCount()

    def get_text(self) -> str:
        """Return text from clipboard

        Returns: str
        """
        return self.pasteboard.stringForType_(NSPasteboardTypeString) or ""

    def get_image(self, filename: t.Union[str, os.PathLike], overwrite: bool = False):
        """Save image from clipboard to filename in PNG format

        Args:
            filename (os.PathLike): Filename of image to save to
            overwrite (bool): Overwrite existing file

        Raises:
            FileExistsError: If file exists and overwrite is False
        """
        if not isinstance(filename, str):
            filename = str(filename)
        if not overwrite and os.path.exists(filename):
            raise FileExistsError(f"File '{filename}' already exists")
        data = self.get_image_data()
        data.writeToFile_atomically_(filename, True)

    def set_image(self, filename: t.Union[str, os.PathLike]):
        """Set image on clipboard from filename

        Args:
            filename (os.PathLike): Filename of image to set on clipboard
        """
        if not isinstance(filename, str):
            filename = str(filename)
        data = NSData.dataWithContentsOfFile_(filename)
        self.set_image_data(data)

    def get_image_data(self) -> NSData:
        """Return image data from clipboard as NSData in PNG format

        Returns: NSData of image in PNG format
        """
        return self.pasteboard.dataForType_(NSPasteboardTypePNG)

    def set_image_data(self, image_data: NSData):
        """Set image data on clipboard from NSData in PNG format

        Args:
            image_data (NSData): Image data to set on clipboard
        """
        self.pasteboard.clearContents()
        self.pasteboard.setData_forType_(image_data, NSPasteboardTypePNG)
        self._change_count = self.pasteboard.changeCount()

    def has_changed(self) -> bool:
        """Return True if clipboard has been changed by another process since last check

        Returns: bool
        """
        if self.pasteboard.changeCount() != self._change_count:
            self._change_count = self.pasteboard.changeCount()
            return True
        return False

    def has_image(self) -> bool:
        """Return True if clipboard has image otherwise False

        Returns: bool
        """
        return self.pasteboard.types().containsObject_(NSPasteboardTypePNG)

    def has_text(self) -> bool:
        """Return True if clipboard has text, otherwise False

        Returns: bool
        """
        return self.pasteboard.types().containsObject_(NSPasteboardTypeString)
