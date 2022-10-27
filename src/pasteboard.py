"""macOS Pasteboard/Clipboard access using native APIs

Author: Rhet Turnbull <rturnbull+git@gmail.com>

License: MIT License, copyright 2022 Rhet Turnbull

Original Source: https://github.com/RhetTbull/textinator

Version: 1.1.0, 2022-10-26
"""

import os
import typing as t

from AppKit import (
    NSPasteboard,
    NSPasteboardTypePNG,
    NSPasteboardTypeString,
    NSPasteboardTypeTIFF,
)
from Foundation import NSData

# shortcuts for types
PNG = "PNG"
TIFF = "TIFF"

__all__ = ["Pasteboard", "PasteboardTypeError", "PNG", "TIFF"]


class PasteboardError(Exception):
    """Base class for Pasteboard exceptions"""

    ...


class PasteboardTypeError(PasteboardError):
    """Invalid type specified"""

    ...


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

    def copy_image(self, filename: t.Union[str, os.PathLike], format: str):
        """Copy image to clipboard from filename

        Args:
            filename (os.PathLike): Filename of image to copy to clipboard
            format (str): Format of image to copy, "PNG" or "TIFF"
        """
        if not isinstance(filename, str):
            filename = str(filename)
        self.set_image(filename, format)

    def paste_image(
        self,
        filename: t.Union[str, os.PathLike],
        format: str,
        overwrite: bool = False,
    ):
        """Paste image from clipboard to filename in PNG format

        Args:
            filename (os.PathLike): Filename of image to paste to
            format (str): Format of image to paste, "PNG" or "TIFF"
            overwrite (bool): Overwrite existing file

        Raises:
            FileExistsError: If file exists and overwrite is False
        """
        if not isinstance(filename, str):
            filename = str(filename)
        self.get_image(filename, format, overwrite)

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

    def get_image(
        self,
        filename: t.Union[str, os.PathLike],
        format: str,
        overwrite: bool = False,
    ):
        """Save image from clipboard to filename in PNG format

        Args:
            filename (os.PathLike): Filename of image to save to
            format (str): Format of image to save, "PNG" or "TIFF"
            overwrite (bool): Overwrite existing file

        Raises:
            FileExistsError: If file exists and overwrite is False
            PasteboardTypeError: If format is not "PNG" or "TIFF"
        """
        if format not in (PNG, TIFF):
            raise PasteboardTypeError("Invalid format, must be PNG or TIFF")

        if not isinstance(filename, str):
            filename = str(filename)

        if not overwrite and os.path.exists(filename):
            raise FileExistsError(f"File '{filename}' already exists")

        data = self.get_image_data(format)
        data.writeToFile_atomically_(filename, True)

    def set_image(self, filename: t.Union[str, os.PathLike], format: str):
        """Set image on clipboard from file in either PNG or TIFF format

        Args:
            filename (os.PathLike): Filename of image to set on clipboard
            format (str): Format of image to set, "PNG" or "TIFF"
        """
        if not isinstance(filename, str):
            filename = str(filename)
        data = NSData.dataWithContentsOfFile_(filename)
        self.set_image_data(data, format)

    def get_image_data(self, format: str) -> NSData:
        """Return image data from clipboard as NSData in PNG or TIFF format

        Args:
            format (str): Format of image to return, "PNG" or "TIFF"

        Returns: NSData of image in PNG or TIFF format

        Raises:
            PasteboardTypeError if clipboard does not contain image in the specified type or type is invalid
        """
        if format not in (PNG, TIFF):
            raise PasteboardTypeError("Invalid format, must be PNG or TIFF")

        pb_type = NSPasteboardTypePNG if format == PNG else NSPasteboardTypeTIFF
        if pb_type == NSPasteboardTypePNG and not self._has_png():
            raise PasteboardTypeError("Clipboard does not contain PNG image")
        return self.pasteboard.dataForType_(pb_type)

    def set_image_data(self, image_data: NSData, format: str):
        """Set image data on clipboard from NSData in a supported image format

        Args:
            image_data (NSData): Image data to set on clipboard
            format (str): Format of image to set, "PNG" or "TIFF"

        Raises: PasteboardTypeError if format is not "PNG" or "TIFF"
        """
        if format not in (PNG, TIFF):
            raise PasteboardTypeError("Invalid format, must be PNG or TIFF")

        format_type = NSPasteboardTypePNG if format == PNG else NSPasteboardTypeTIFF
        self.pasteboard.clearContents()
        self.pasteboard.setData_forType_(image_data, format_type)
        self._change_count = self.pasteboard.changeCount()

    def set_text_and_image(
        self, text: str, filename: t.Union[str, os.PathLike], format: str
    ):
        """Set both text from str and image from file in either PNG or TIFF format

        Args:
            text (str): Text to set on clipboard
            filename (os.PathLike): Filename of image to set on clipboard
            format (str): Format of image to set, "PNG" or "TIFF"
        """
        if not isinstance(filename, str):
            filename = str(filename)
        data = NSData.dataWithContentsOfFile_(filename)
        self.set_text_and_image_data(text, data, format)

    def set_text_and_image_data(self, text: str, image_data: NSData, format: str):
        """Set both text and image data on clipboard from NSData in a supported image format

        Args:
            text (str): Text to set on clipboard
            image_data (NSData): Image data to set on clipboard
            format (str): Format of image to set, "PNG" or "TIFF"

        Raises: PasteboardTypeError if format is not "PNG" or "TIFF"
        """
        self.set_image_data(image_data, format)
        self.pasteboard.setString_forType_(text, NSPasteboardTypeString)
        self._change_count = self.pasteboard.changeCount()

    def has_changed(self) -> bool:
        """Return True if clipboard has been changed by another process since last check

        Returns: bool
        """
        if self.pasteboard.changeCount() != self._change_count:
            self._change_count = self.pasteboard.changeCount()
            return True
        return False

    def has_image(self, format: t.Optional[str] = None) -> bool:
        """Return True if clipboard has image otherwise False

        Args:
            format (str): Format of image to check for, "PNG" or "TIFF" or None to check for any image

        Returns:
            True if clipboard has image otherwise False

        Raises:
            PasteboardTypeError if format is not "PNG" or "TIFF"
        """
        if format is None:
            return self.pasteboard.types().containsObject_(
                NSPasteboardTypeTIFF
            ) or self.pasteboard.types().containsObject_(NSPasteboardTypePNG)
        elif format == PNG:
            return self._has_png()
        elif format == TIFF:
            return self._has_tiff()
        else:
            raise PasteboardTypeError("Invalid format, must be PNG or TIFF")

    def has_text(self) -> bool:
        """Return True if clipboard has text, otherwise False

        Returns: bool
        """
        return self.pasteboard.types().containsObject_(NSPasteboardTypeString)

    def _has_png(self) -> bool:
        """Return True if clipboard can paste PNG image otherwise False

        Returns: bool
        """
        return bool(self.pasteboard.availableTypeFromArray_([NSPasteboardTypePNG]))

    def _has_tiff(self) -> bool:
        """Return True if clipboard can paste TIFF image otherwise False

        Returns: bool
        """
        return bool(self.pasteboard.availableTypeFromArray_([NSPasteboardTypeTIFF]))
