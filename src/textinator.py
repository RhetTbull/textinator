"""Simple MacOS menu bar / status bar app that automatically perform text detection on screenshots.

Runs on Catalina (10.15) and later.
"""

import contextlib
import datetime
import plistlib
import typing as t

import objc
import Quartz
import rumps
from AppKit import NSPasteboardTypeFileURL
from Foundation import (
    NSURL,
    NSLog,
    NSMetadataQuery,
    NSMetadataQueryDidFinishGatheringNotification,
    NSMetadataQueryDidStartGatheringNotification,
    NSMetadataQueryDidUpdateNotification,
    NSMetadataQueryGatheringProgressNotification,
    NSNotificationCenter,
    NSObject,
    NSPredicate,
    NSString,
    NSUTF8StringEncoding,
)

from loginitems import add_login_item, list_login_items, remove_login_item
from macvision import (
    ciimage_from_file,
    detect_qrcodes_in_ciimage,
    detect_text_in_ciimage,
    get_supported_vision_languages,
)
from pasteboard import TIFF, Pasteboard
from utils import get_app_path, verify_desktop_access

__version__ = "0.9.0"

APP_NAME = "Textinator"
APP_ICON = "icon.png"
APP_ICON_PAUSED = "icon_paused.png"

# default confidence threshold for text detection
CONFIDENCE = {"LOW": 0.3, "MEDIUM": 0.5, "HIGH": 0.8}
CONFIDENCE_DEFAULT = "LOW"

# default language for text detection
LANGUAGE_DEFAULT = "en-US"
LANGUAGE_ENGLISH = "en-US"

# where to store saved state, will reside in Application Support/APP_NAME
CONFIG_FILE = f"{APP_NAME}.plist"

# optional logging to file if debug enabled (will always log to console via NSLog)
LOG_FILE = f"{APP_NAME}.log"

# how often (in seconds) to check for new screenshots on the clipboard
CLIPBOARD_CHECK_INTERVAL = 2


class Textinator(rumps.App):
    """MacOS Menu Bar App to automatically perform text detection on screenshots."""

    def __init__(self, *args, **kwargs):
        super(Textinator, self).__init__(*args, **kwargs)

        # set "debug" to true in the config file to enable debug logging
        self._debug = False

        # pause / resume text detection
        self._paused = False

        self.icon = APP_ICON
        self.log("started")

        # get list of supported languages for language menu
        languages, _ = get_supported_vision_languages()
        languages = languages or [LANGUAGE_DEFAULT]
        self.log(f"supported languages: {languages}")
        self.recognition_language = (
            LANGUAGE_DEFAULT if LANGUAGE_DEFAULT in languages else languages[0]
        )

        # menus
        self.confidence = rumps.MenuItem("Text detection confidence threshold")
        self.confidence_low = rumps.MenuItem("Low", self.on_confidence)
        self.confidence_medium = rumps.MenuItem("Medium", self.on_confidence)
        self.confidence_high = rumps.MenuItem("High", self.on_confidence)
        self.language = rumps.MenuItem("Text recognition language")
        for language in languages:
            self.language.add(rumps.MenuItem(language, self.on_language))
        self.language_english = rumps.MenuItem("Always detect English", self.on_toggle)
        self.detect_clipboard = rumps.MenuItem(
            "Detect text in images on clipboard", self.on_toggle
        )
        self.qrcodes = rumps.MenuItem("Detect QR codes", self.on_toggle)
        self.pause = rumps.MenuItem("Pause text detection", self.on_pause)
        self.notification = rumps.MenuItem("Notification", self.on_toggle)
        self.linebreaks = rumps.MenuItem("Keep linebreaks", self.on_toggle)
        self.append = rumps.MenuItem("Append to clipboard", self.on_toggle)
        self.clear_clipboard = rumps.MenuItem(
            "Clear Clipboard", self.on_clear_clipboard
        )
        self.confirmation = rumps.MenuItem("Confirm clipboard changes", self.on_toggle)
        self.start_on_login = rumps.MenuItem(
            f"Start {APP_NAME} on login", self.on_start_on_login
        )
        self.about = rumps.MenuItem(f"About {APP_NAME}", self.on_about)
        self.quit = rumps.MenuItem(f"Quit {APP_NAME}", self.on_quit)
        self.menu = [
            [
                self.confidence,
                [self.confidence_low, self.confidence_medium, self.confidence_high],
            ],
            self.language,
            self.language_english,
            self.detect_clipboard,
            self.pause,
            None,
            self.qrcodes,
            None,
            self.notification,
            None,
            self.linebreaks,
            self.append,
            self.clear_clipboard,
            self.confirmation,
            None,
            self.start_on_login,
            self.about,
            self.quit,
        ]

        # load config from plist file and init menu state
        self.load_config()

        # holds all screenshots already seen
        self._screenshots = {}

        # Need to verify access to the Desktop folder which is the default location for screenshots
        # When this is called for the first time, the user will be prompted to grant access
        # and shown the message assigned to NSDesktopFolderUsageDescription in the Info.plist file
        verify_desktop_access()

        self.log(__file__)

        from AppKit import NSApplication

        self.service_provider = ServiceProvider.alloc().initWithApp_(self)
        NSApplication.sharedApplication().setServicesProvider_(self.service_provider)

        # This will be used by clipboard_watcher() to detect changes to the pasteboard
        # (which everyone but Apple calls the clipboard)
        self.pasteboard = Pasteboard()

        # start the spotlight query
        self.start_query()

    def log(self, msg: str):
        """Log a message to unified log."""
        NSLog(f"{APP_NAME} {__version__} {msg}")

        # if debug set in config, also log to file
        # file will be created in Application Support folder
        if self._debug:
            with self.open(LOG_FILE, "a") as f:
                f.write(f"{datetime.datetime.now().isoformat()} - {msg}\n")

    def load_config(self):
        """Load config from plist file in Application Support folder."""
        self.config = {}
        with contextlib.suppress(FileNotFoundError):
            with self.open(CONFIG_FILE, "rb") as f:
                with contextlib.suppress(Exception):
                    # don't crash if config file is malformed
                    self.config = plistlib.load(f)
        if not self.config:
            # file didn't exist or was malformed, create a new one
            # initialize config with default values
            self.config = {
                "confidence": CONFIDENCE_DEFAULT,
                "linebreaks": True,
                "append": False,
                "notification": True,
                "language": self.recognition_language,
                "always_detect_english": True,
                "detect_qrcodes": False,
                "start_on_login": False,
                "confirmation": False,
                "detect_clipboard": True,
            }
        self.log(f"loaded config: {self.config}")
        self.append.state = self.config.get("append", False)
        self.linebreaks.state = self.config.get("linebreaks", True)
        self.notification.state = self.config.get("notification", True)
        self.set_confidence_state(self.config.get("confidence", CONFIDENCE_DEFAULT))
        self.recognition_language = self.config.get(
            "language", self.recognition_language
        )
        self.set_language_menu_state(self.recognition_language)
        self.language_english.state = self.config.get("always_detect_english", True)
        self.detect_clipboard.state = self.config.get("detect_clipboard", True)
        self.confirmation.state = self.config.get("confirmation", False)
        self.qrcodes.state = self.config.get("detect_qrcodes", False)
        self._debug = self.config.get("debug", False)
        self.start_on_login.state = self.config.get("start_on_login", False)
        self.save_config()

    def save_config(self):
        """Write config to plist file in Application Support folder."""
        self.config["linebreaks"] = self.linebreaks.state
        self.config["append"] = self.append.state
        self.config["notification"] = self.notification.state
        self.config["confidence"] = self.get_confidence_state()
        self.config["language"] = self.recognition_language
        self.config["always_detect_english"] = self.language_english.state
        self.config["detect_clipboard"] = self.detect_clipboard.state
        self.config["confirmation"] = self.confirmation.state
        self.config["detect_qrcodes"] = self.qrcodes.state
        self.config["debug"] = self._debug
        self.config["start_on_login"] = self.start_on_login.state
        with self.open(CONFIG_FILE, "wb+") as f:
            plistlib.dump(self.config, f)
        self.log(f"saved config: {self.config}")

    def on_language(self, sender):
        """Change language."""
        self.recognition_language = sender.title
        self.set_language_menu_state(sender.title)
        self.save_config()

    def on_pause(self, sender):
        """Pause/resume text detection."""
        if self._paused:
            self._paused = False
            self.icon = APP_ICON
            sender.title = "Pause text detection"
        else:
            self._paused = True
            self.icon = APP_ICON_PAUSED
            sender.title = "Resume text detection"

    def on_toggle(self, sender):
        """Toggle sender state."""
        sender.state = not sender.state
        self.save_config()

    def on_clear_clipboard(self, sender):
        """Clear the clipboard"""
        self.pasteboard.clear()

    def on_confidence(self, sender):
        """Change confidence threshold."""
        self.clear_confidence_state()
        sender.state = True
        self.save_config()

    def clear_confidence_state(self):
        """Clear confidence menu state"""
        self.confidence_low.state = False
        self.confidence_medium.state = False
        self.confidence_high.state = False

    def get_confidence_state(self):
        """Get confidence threshold state."""
        if self.confidence_low.state:
            return "LOW"
        elif self.confidence_medium.state:
            return "MEDIUM"
        elif self.confidence_high.state:
            return "HIGH"
        else:
            return CONFIDENCE_DEFAULT

    def set_confidence_state(self, confidence):
        """Set confidence threshold state."""
        self.clear_confidence_state()
        if confidence == "LOW":
            self.confidence_low.state = True
        elif confidence == "MEDIUM":
            self.confidence_medium.state = True
        elif confidence == "HIGH":
            self.confidence_high.state = True
        else:
            raise ValueError(f"Unknown confidence threshold: {confidence}")

    def set_language_menu_state(self, language):
        """Set the language menu state"""
        for item in self.language.values():
            item.state = False
            if item.title == language:
                item.state = True

    def start_query(self):
        """Start the NSMetdataQuery Spotlight query."""
        self.query = NSMetadataQuery.alloc().init()

        # screenshots all have kMDItemIsScreenCapture set
        self.query.setPredicate_(
            NSPredicate.predicateWithFormat_("kMDItemIsScreenCapture = 1")
        )

        # configure the query to post notifications, which our query_updated method will handle
        nf = NSNotificationCenter.defaultCenter()
        nf.addObserver_selector_name_object_(
            self,
            "query_updated:",
            None,
            self.query,
        )
        self.query.setDelegate_(self)
        self.query.startQuery()

    def on_start_on_login(self, sender):
        """Configure app to start on login or toggle this setting."""
        self.start_on_login.state = not self.start_on_login.state
        if self.start_on_login.state:
            app_path = get_app_path()
            self.log(f"adding app to login items with path {app_path}")
            if APP_NAME not in list_login_items():
                add_login_item(APP_NAME, app_path, hidden=False)
        else:
            self.log("removing app from login items")
            if APP_NAME in list_login_items():
                remove_login_item(APP_NAME)
        self.save_config()

    def on_about(self, sender):
        """Display about dialog."""
        rumps.alert(
            title=f"About {APP_NAME}",
            message=f"{APP_NAME} Version {__version__}\n\n"
            f"{APP_NAME} is a simple utility to recognize text in screenshots.\n\n"
            f"{APP_NAME} is open source and licensed under the MIT license.\n\n"
            "Copyright 2022 by Rhet Turnbull\n"
            "https://github.com/RhetTbull/textinator",
            ok="OK",
        )

    def on_quit(self, sender):
        """Cleanup before quitting."""
        self.log("quitting")
        NSNotificationCenter.defaultCenter().removeObserver_(self)
        self.query.stopQuery()
        self.query.setDelegate_(None)
        self.query.release()
        rumps.quit_application()

    def initialize_screenshots(self, notif):
        """Track all screenshots already seen or that existed on app startup.

        The Spotlight query will return *all* screenshots on the computer so track those results
        when returned and only process new screenshots.
        """
        results = notif.object().results()
        for item in results:
            path = item.valueForAttribute_(
                "kMDItemPath"
            ).stringByResolvingSymlinksInPath()
            self._screenshots[path] = True

    def process_screenshot(self, notif):
        """Process a new screenshot and detect text (and QR codes if requested)."""
        results = notif.object().results()
        for item in results:
            path = item.valueForAttribute_(
                "kMDItemPath"
            ).stringByResolvingSymlinksInPath()

            if path in self._screenshots:
                # we've already seen this screenshot or screenshot existed at app startup, skip it
                continue

            if self._paused:
                # don't process screenshots if paused
                self.log(f"skipping screenshot because app is paused: {path}")
                self._screenshots[path] = "__SKIPPED__"
                continue

            self.log(f"processing new screenshot: {path}")

            screenshot_image = ciimage_from_file(path)
            if screenshot_image is None:
                self.log(f"failed to load screenshot image: {path}")
                continue

            detected_text = self.process_image(screenshot_image)
            if self.notification.state:
                rumps.notification(
                    title="Processed Screenshot",
                    subtitle=f"{path}",
                    message=f"Detected text: {detected_text}"
                    if detected_text
                    else "No text detected",
                )
            self._screenshots[path] = detected_text

    def process_image(self, image: Quartz.CIImage) -> str:
        """Process an image and detect text (and QR codes if requested).

        Args:
            image: Quartz.CIImage
            path: Optional path to the image file (used for logging)

        Returns:
            String of detected text or empty string if no text detected.
        """
        # if "Always detect English" checked, add English to list of languages to detect
        languages = (
            [self.recognition_language, LANGUAGE_ENGLISH]
            if self.language_english.state
            and self.recognition_language != LANGUAGE_ENGLISH
            else [self.recognition_language]
        )
        detected_text = detect_text_in_ciimage(image, languages=languages)
        confidence = CONFIDENCE[self.get_confidence_state()]
        text = "\n".join(
            result[0] for result in detected_text if result[1] >= confidence
        )

        if self.qrcodes.state:
            # Also detect QR codes and copy the text from the QR code payload
            if detected_qrcodes := detect_qrcodes_in_ciimage(image):
                text = (
                    text + "\n" + "\n".join(detected_qrcodes)
                    if text
                    else "\n".join(detected_qrcodes)
                )

        if text:
            if not self.linebreaks.state:
                text = text.replace("\n", " ")
            # Note: only log the fact that text was detected, not the text itself
            # as sometimes the mere fact of logging certain text causes the process to hang
            # I have no idea why this happens but it's reproducible
            detected_text = True
            if self.append.state:
                clipboard_text = (
                    self.pasteboard.paste() if self.pasteboard.has_text() else ""
                )
                clipboard_text = f"{clipboard_text}\n{text}" if clipboard_text else text
            else:
                clipboard_text = text

            if self.confirmation.state:
                # display confirmation dialog
                verb = "Append" if self.append.state else "Copy"
                if rumps.alert(
                    title=f"{verb} detected text to clipboard?",
                    message=text,
                    ok="Yes",
                    cancel="No",
                ):
                    self.pasteboard.copy(clipboard_text)
            else:
                self.pasteboard.copy(clipboard_text)

        return text

    def query_updated_(self, notif):
        """Receives and processes notifications from the Spotlight query"""
        if notif.name() == NSMetadataQueryDidStartGatheringNotification:
            # The query has just started
            self.log("search: query started")
        elif notif.name() == NSMetadataQueryDidFinishGatheringNotification:
            # The query has just finished
            # log all results so we don't try to do text detection on previous screenshots
            self.log("search: finished gathering")
            self.initialize_screenshots(notif)
        elif notif.name() == NSMetadataQueryGatheringProgressNotification:
            # The query is still gathering results...
            self.log("search: gathering progress")
        elif notif.name() == NSMetadataQueryDidUpdateNotification:
            # There's a new result available
            self.log("search: an update happened.")
            self.process_screenshot(notif)

    @rumps.timer(CLIPBOARD_CHECK_INTERVAL)
    def clipboard_watcher(self, sender):
        """Watch the clipboard (pasteboard) for changes"""
        if not self.detect_clipboard.state:
            return

        if self.pasteboard.has_changed() and self.pasteboard.has_image():
            # image is on the pasteboard, process it
            self.log("new image on clipboard")
            if self._paused:
                self.log("skipping clipboard image because app is paused")
                return
            self.process_clipboard_image()

    def process_clipboard_image(self):
        """Process the image on the clipboard."""
        if image_data := self.pasteboard.get_image_data(TIFF):
            image = Quartz.CIImage.imageWithData_(image_data)
            detected_text = self.process_image(image)
            self.log("processed clipboard image")
            if self.notification.state:
                rumps.notification(
                    title="Processed Clipboard Image",
                    subtitle="",
                    message=f"Detected text: {detected_text}"
                    if detected_text
                    else "No text detected",
                )
        else:
            self.log("failed to get image data from pasteboard")


def serviceSelector(fn):
    # this is the signature of service selectors
    return objc.selector(fn, signature=b"v@:@@o^@")


def ErrorValue(e):
    """Handler for errors returned by the service."""
    NSLog(f"{APP_NAME} {__version__} error: {e}")
    return e


class ServiceProvider(NSObject):
    """Service provider class to handle messages from the Services menu

    Initialize with ServiceProvider.alloc().initWithApp_(app)
    """

    app: t.Optional[Textinator] = None

    def initWithApp_(self, app: Textinator):
        self = objc.super(ServiceProvider, self).init()
        self.app = app
        return self

    @serviceSelector
    def detectTextInImage_userData_error_(self, pasteboard, userdata, error) -> None:
        """Detect text in an image on the clipboard."""
        self.app.log("detectTextInImage_userData_error_ called via Services menu")

        if self.app._paused:
            self.app.log("skipping text detection because app is paused")

        try:
            for item in pasteboard.pasteboardItems():
                pb_url_data = item.dataForType_(NSPasteboardTypeFileURL)
                pb_url = NSURL.URLWithString_(
                    NSString.alloc().initWithData_encoding_(
                        pb_url_data, NSUTF8StringEncoding
                    )
                )
                self.app.log(f"processing file from Services menu: {pb_url.path()}")
                image = Quartz.CIImage.imageWithContentsOfURL_(pb_url)
                self.app.process_image(image)
        except Exception as e:
            return ErrorValue(e)

        return None


if __name__ == "__main__":
    Textinator(name=APP_NAME, quit_button=None).run()
