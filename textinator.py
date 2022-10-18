"""Simple MacOS menu bar / status bar app that automatically perform text detection on screenshots.

Runs on Catalina (10.15) and later.
"""

import contextlib
import datetime
import os
import platform
import plistlib
from typing import List, Optional, Tuple

import applescript
import objc
import pyperclip
import Quartz
import rumps
import Vision
from Foundation import (
    NSURL,
    NSBundle,
    NSDesktopDirectory,
    NSDictionary,
    NSFileManager,
    NSLog,
    NSMetadataQuery,
    NSMetadataQueryDidFinishGatheringNotification,
    NSMetadataQueryDidStartGatheringNotification,
    NSMetadataQueryDidUpdateNotification,
    NSMetadataQueryGatheringProgressNotification,
    NSNotificationCenter,
    NSPredicate,
    NSUserDomainMask,
)

__version__ = "0.8.1"

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
        self.qrcodes = rumps.MenuItem("Detect QR codes", self.on_toggle)
        self.pause = rumps.MenuItem("Pause text detection", self.on_pause)
        self.notification = rumps.MenuItem("Notification", self.on_toggle)
        self.linebreaks = rumps.MenuItem("Keep linebreaks", self.on_toggle)
        self.append = rumps.MenuItem("Append to clipboard", self.on_toggle)
        self.clear_clipboard = rumps.MenuItem(
            "Clear Clipboard", self.on_clear_clipboard
        )
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
            self.pause,
            None,
            self.qrcodes,
            None,
            self.notification,
            None,
            self.linebreaks,
            self.append,
            self.clear_clipboard,
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
        pyperclip.copy("")

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

            # if "Always detect English" checked, add English to list of languages to detect
            languages = (
                [self.recognition_language, LANGUAGE_ENGLISH]
                if self.language_english.state
                and self.recognition_language != LANGUAGE_ENGLISH
                else [self.recognition_language]
            )
            detected_text = detect_text(path, languages=languages)
            confidence = CONFIDENCE[self.get_confidence_state()]
            text = "\n".join(
                result[0] for result in detected_text if result[1] >= confidence
            )

            if self.qrcodes.state:
                # Also detect QR codes and copy the text from the QR code payload
                if detected_qrcodes := detect_qrcodes(path):
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
                self.log(f"detected text in {path}")
                text = (
                    f"{pyperclip.paste()}\n{text}"
                    if self.append.state and pyperclip.paste()
                    else text
                )
                pyperclip.copy(text)
            else:
                self.log(f"detected no text in {path}")
            if self.notification.state:
                rumps.notification(
                    title="Processed Screenshot",
                    subtitle=f"{path}",
                    message=f"Detected text: {text}" if text else "No text detected",
                )
            self._screenshots[path] = text

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


def get_supported_vision_languages() -> Tuple[Tuple[str], Tuple[str]]:
    """Get supported languages for text detection from Vision framework.

    Returns: Tuple of ((language code), (error))
    """

    with objc.autorelease_pool():
        revision = Vision.VNRecognizeTextRequestRevision1
        if get_mac_os_version() >= ("11", "0", "0"):
            revision = Vision.VNRecognizeTextRequestRevision2

        if get_mac_os_version() < ("12", "0", "0"):
            return Vision.VNRecognizeTextRequest.supportedRecognitionLanguagesForTextRecognitionLevel_revision_error_(
                Vision.VNRequestTextRecognitionLevelAccurate, revision, None
            )

        results = []
        handler = make_request_handler(results)
        textRequest = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(
            handler
        )
        return textRequest.supportedRecognitionLanguagesAndReturnError_(None)


def detect_text(
    img_path: str,
    orientation: Optional[int] = None,
    languages: Optional[List[str]] = None,
) -> List:
    """process image at img_path with VNRecognizeTextRequest and return list of results

    This code originally developed for https://github.com/RhetTbull/osxphotos

    Args:
        img_path: path to the image file
        orientation: optional EXIF orientation (if known, passing orientation may improve quality of results)
        languages: optional languages to use for text detection as list of ISO language code strings; default is ["en-US"]
    """
    with objc.autorelease_pool():
        input_url = NSURL.fileURLWithPath_(img_path)

        # create a CIIImage from the image at img_path as that's what Vision wantsß
        input_image = Quartz.CIImage.imageWithContentsOfURL_(input_url)

        vision_options = NSDictionary.dictionaryWithDictionary_({})
        if orientation is None:
            vision_handler = (
                Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
                    input_image, vision_options
                )
            )
        elif 1 <= orientation <= 8:
            vision_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_orientation_options_(
                input_image, orientation, vision_options
            )
        else:
            raise ValueError("orientation must be between 1 and 8")
        results = []
        handler = make_request_handler(results)
        vision_request = (
            Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
        )
        languages = languages or ["en-US"]
        vision_request.setRecognitionLanguages_(languages)
        vision_request.setUsesLanguageCorrection_(True)
        success, error = vision_handler.performRequests_error_([vision_request], None)
        if not success:
            raise ValueError(f"Vision request failed: {error}")

        for result in results:
            result[0] = str(result[0])

        return results


def make_request_handler(results):
    """results: list to store results"""
    if not isinstance(results, list):
        raise ValueError("results must be a list")

    def handler(request, error):
        if error:
            NSLog(f"{APP_NAME} Error! {error}")
        else:
            observations = request.results()
            for text_observation in observations:
                recognized_text = text_observation.topCandidates_(1)[0]
                results.append([recognized_text.string(), recognized_text.confidence()])

    return handler


def detect_qrcodes(filepath: str) -> List[str]:
    """Detect QR Codes in images using CIDetector and return text of the found QR Codes"""
    with objc.autorelease_pool():
        context = Quartz.CIContext.contextWithOptions_(None)
        options = NSDictionary.dictionaryWithDictionary_(
            {"CIDetectorAccuracy": Quartz.CIDetectorAccuracyHigh}
        )
        detector = Quartz.CIDetector.detectorOfType_context_options_(
            Quartz.CIDetectorTypeQRCode, context, options
        )

        results = []
        input_url = NSURL.fileURLWithPath_(filepath)
        input_image = Quartz.CIImage.imageWithContentsOfURL_(input_url)
        features = detector.featuresInImage_(input_image)

        if not features:
            return []
        for idx in range(features.count()):
            feature = features.objectAtIndex_(idx)
            results.append(feature.messageString())
        return results


def get_app_path() -> str:
    """Return path to the bundle containing this script"""
    # Note: This must be called from an app bundle built with py2app or you'll get
    # the path of the python interpreter instead of the actual app
    return NSBundle.mainBundle().bundlePath()


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


if __name__ == "__main__":
    Textinator(name=APP_NAME, quit_button=None).run()
