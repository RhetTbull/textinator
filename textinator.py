"""Simple MacOS menu bar app automatically perform text detection on screenshots.

Runs on Catalina (10.15) and later.
"""

import contextlib
import platform
import plistlib
from typing import List, Optional, Tuple

import objc
import pyperclip
import Quartz
import rumps
import Vision
from Cocoa import NSURL
from Foundation import (
    NSDictionary,
    NSLog,
    NSMetadataQuery,
    NSMetadataQueryDidFinishGatheringNotification,
    NSMetadataQueryDidStartGatheringNotification,
    NSMetadataQueryDidUpdateNotification,
    NSMetadataQueryGatheringProgressNotification,
    NSNotificationCenter,
    NSPredicate,
)
from wurlitzer import pipes

__version__ = "0.3.0"

APP_NAME = "Textinator"
APP_ICON = "icon.png"

# default confidence threshold for text detection
CONFIDENCE = {"LOW": 0.3, "MEDIUM": 0.5, "HIGH": 0.8}
CONFIDENCE_DEFAULT = "LOW"

# where to store saved state, will reside in Application Support/APP_NAME
CONFIG_FILE = f"{APP_NAME}.plist"


class Textinator(rumps.App):
    """MacOS Menu Bar App to automatically perform text detection on screenshots."""

    def __init__(self, *args, **kwargs):
        super(Textinator, self).__init__(*args, **kwargs)

        self.icon = APP_ICON

        # get list of supported languages for language menu
        languages, _ = get_supported_vision_languages()
        languages = languages or ["en-US"]
        NSLog(f"{APP_NAME} supported languages: {languages}")
        self.recognition_language = languages[0]

        # menus
        self.confidence = rumps.MenuItem("Text detection confidence threshold")
        self.confidence_low = rumps.MenuItem("Low", self.on_confidence)
        self.confidence_medium = rumps.MenuItem("Medium", self.on_confidence)
        self.confidence_high = rumps.MenuItem("High", self.on_confidence)
        self.language = rumps.MenuItem("Text recognition language")
        for language in languages:
            self.language.add(rumps.MenuItem(language, self.on_language))
        self.notification = rumps.MenuItem("Notification", self.on_toggle)
        self.linebreaks = rumps.MenuItem("Keep linebreaks", self.on_toggle)
        self.append = rumps.MenuItem("Append to clipboard", self.on_toggle)
        self.clear_clipboard = rumps.MenuItem(
            "Clear Clipboard", self.on_clear_clipboard
        )
        self.about = rumps.MenuItem(f"About {APP_NAME}", self.on_about)
        self.quit = rumps.MenuItem(f"Quit {APP_NAME}", self.on_quit)
        self.menu = [
            [
                self.confidence,
                [self.confidence_low, self.confidence_medium, self.confidence_high],
            ],
            self.language,
            None,
            self.notification,
            None,
            self.linebreaks,
            self.append,
            self.clear_clipboard,
            None,
            self.about,
            self.quit,
        ]

        # load config from plist file and init menu state
        self.load_config()

        # holds all screenshots already seen
        self._screenshots = {}

        # start the spotlight query
        self.start_query()

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
            }
        NSLog(f"{APP_NAME} loaded config: {self.config}")
        self.append.state = self.config["append"]
        self.linebreaks.state = self.config["linebreaks"]
        self.notification.state = self.config["notification"]
        self.set_confidence_state(self.config["confidence"])
        self.recognition_language = self.config.get(
            "language", self.recognition_language
        )
        self.set_language_menu_state(self.recognition_language)
        self.save_config()

    def save_config(self):
        """Write config to plist file in Application Support folder."""
        self.config["linebreaks"] = self.linebreaks.state
        self.config["append"] = self.append.state
        self.config["notification"] = self.notification.state
        self.config["confidence"] = self.get_confidence_state()
        self.config["language"] = self.recognition_language
        with self.open(CONFIG_FILE, "wb+") as f:
            plistlib.dump(self.config, f)
        NSLog(f"{APP_NAME} saved config: {self.config}")

    def on_language(self, sender):
        """Change language."""
        self.recognition_language = sender.title
        self.set_language_menu_state(sender.title)
        self.save_config()

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
        """Process a new screenshot and detect text."""
        results = notif.object().results()
        for item in results:
            path = item.valueForAttribute_(
                "kMDItemPath"
            ).stringByResolvingSymlinksInPath()
            if path in self._screenshots:
                # we've already seen this screenshot or screenshot existed at app startup, skip it
                continue
            detected_text = detect_text(path, languages=[self.recognition_language])
            confidence = CONFIDENCE[self.get_confidence_state()]
            text = "\n".join(
                result[0] for result in detected_text if result[1] >= confidence
            )

            if text:
                if not self.linebreaks.state:
                    text = text.replace("\n", " ")
                NSLog(f"{APP_NAME} detected text: {text}")
                text = (
                    f"{pyperclip.paste()}\n{text}"
                    if self.append.state and pyperclip.paste()
                    else text
                )
                pyperclip.copy(text)
            else:
                NSLog(f"{APP_NAME} detected no text in {path}")
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
            NSLog(f"{APP_NAME} search: query started")
        elif notif.name() == NSMetadataQueryDidFinishGatheringNotification:
            # The query has just finished
            # log all results so we don't try to do text detection on previous screenshots
            NSLog(f"{APP_NAME} search: finished gathering")
            self.initialize_screenshots(notif)
        elif notif.name() == NSMetadataQueryGatheringProgressNotification:
            # The query is still gathering results...
            NSLog(f"{APP_NAME} search: gathering progress")
        elif notif.name() == NSMetadataQueryDidUpdateNotification:
            # There's a new result available
            NSLog(f"{APP_NAME} search: an update happened.")
            self.process_screenshot(notif)


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
    if ver == "10":
        if major == "16":
            ver = "11"
            major = minor
            minor = "0"
        elif major == "17":
            ver = "12"
            major = minor
            minor = "0"
        elif major == "18":
            ver = "13"
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
        textRequest = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler(
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

        with pipes() as (out, err):
            # capture stdout and stderr from system calls
            # otherwise, Quartz.CIImage.imageWithContentsOfURL_
            # prints to stderr something like:
            # 2020-09-20 20:55:25.538 python[73042:5650492] Creating client/daemon connection: B8FE995E-3F27-47F4-9FA8-559C615FD774
            # 2020-09-20 20:55:25.652 python[73042:5650492] Got the query meta data reply for: com.apple.MobileAsset.RawCamera.Camera, response: 0
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
        error = vision_handler.performRequests_error_([vision_request], None)
        vision_request.dealloc()
        vision_handler.dealloc()

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


if __name__ == "__main__":
    Textinator(name=APP_NAME, quit_button=None).run()
