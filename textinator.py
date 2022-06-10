"""Simple MacOS status bar app automatically perform text detection on screenshots.

Runs on Catalina (10.15) and later.
"""

import plistlib
import contextlib
from typing import List, Optional

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

APP_NAME = "Textinator"
ICON = "icon.png"
# default confidence threshold for text detection
DEFAULT_CONFIDENCE = 0.5

# where to store saved state, will reside in Application Support/APP_NAME
CONFIG_FILE = f"{APP_NAME}.plist"


class Textinator(rumps.App):
    def __init__(self, *args, **kwargs):
        super(Textinator, self).__init__(*args, **kwargs)

        self.icon = ICON
        self.load_config()

        # menus
        self.confidence = rumps.MenuItem(
            f"Text Detection Confidence Threshold: {self.config['confidence_threshold']:.2f}",
        )
        self.confidence_slider = rumps.SliderMenuItem(
            value=DEFAULT_CONFIDENCE,
            min_value=0,
            max_value=1,
            callback=self.on_confidence,
        )
        self.append = rumps.MenuItem("Append to Clipboard", callback=self.on_append)
        self.notification = rumps.MenuItem(
            "Notification", callback=self.on_notification
        )
        self.quit = rumps.MenuItem("Quit Textinator", callback=self.on_quit)
        self.menu = [
            self.confidence,
            self.confidence_slider,
            self.append,
            self.notification,
            self.quit,
        ]

        # append to Clipboard
        self.append.state = self.config["append"]

        # show notifications
        self.notification.state = self.config["notification"]

        # holds all screenshots already seen
        self._screenshots = {}

        # confidence threshold for text detection
        self.confidence_threshold = DEFAULT_CONFIDENCE

        # Start the spotlight query
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
                "confidence_threshold": DEFAULT_CONFIDENCE,
                "append": False,
                "notification": True,
            }
            self.save_config()

    def save_config(self):
        """Write config to plist file in Application Support folder."""
        with self.open(CONFIG_FILE, "wb+") as f:
            plistlib.dump(self.config, f)
        print(f"Saved config: {self.config}")

    def on_append(self, sender):
        """Toggle append to clipboard."""
        sender.state = not sender.state
        self.config["append"] = sender.state
        self.save_config()

    def on_confidence(self, sender):
        """Change confidence threshold."""
        self.confidence.title = (
            f"Text detection confidence threshold: {sender.value:.2f}"
        )
        self.confidence_threshold = float(f"{sender.value:.2f}")
        self.config["confidence_threshold"] = self.confidence_threshold
        self.save_config()

    def on_notification(self, sender):
        """Toggle alert/notification"""
        sender.state = not sender.state
        self.config["notification"] = sender.state
        self.save_config()

    def start_query(self):
        """Start the NSMetdataQuery Spotlight query."""
        self.query = NSMetadataQuery.alloc().init()

        # screenshots all have kMDItemIsScreenCapture set
        self.query.setPredicate_(
            NSPredicate.predicateWithFormat_("kMDItemIsScreenCapture = 1")
        )

        # configure the query to post notifications, which our queryUpdated method will handle
        nf = NSNotificationCenter.defaultCenter()
        nf.addObserver_selector_name_object_(
            self,
            "queryUpdated:",
            None,
            self.query,
        )
        self.query.setDelegate_(self)
        self.query.startQuery()

    def on_quit(self, sender):
        """Cleanup before quitting."""
        NSNotificationCenter.defaultCenter().removeObserver_(self)
        self.query.stopQuery()
        self.query.setDelegate_(None)
        self.query.release()
        rumps.quit_application()

    def initialize_screenshots(self, notif):
        """Track all screenshots already seen or that existed on app startup."""
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
                continue
            NSLog(f"New screenshot: {path}")
            detected_text = detect_text(path)
            NSLog(f"Detected text: {detected_text}")
            text = "\n".join(
                result[0]
                for result in detected_text
                if result[1] > self.confidence_threshold
            )

            if text:
                text = f"{pyperclip.paste()}\n{text}" if self.append.state else text
                pyperclip.copy(text)
                if self.notification.state:
                    rumps.notification(
                        title="Processed Screenshot",
                        subtitle=f"{path}",
                        message=f"Detected text: {text}",
                    )
            self._screenshots[path] = text

    def queryUpdated_(self, notif):
        """Receives and processes notifications from the Spotlight query"""
        if notif.name() == NSMetadataQueryDidStartGatheringNotification:
            # The query has just started
            NSLog("search: query started")
        elif notif.name() == NSMetadataQueryDidFinishGatheringNotification:
            # The query has just finished
            # log all results so we don't try to do text detection on previous screenshots
            NSLog("search: finished gathering")
            self.initialize_screenshots(notif)
        elif notif.name() == NSMetadataQueryGatheringProgressNotification:
            # The query is still gathering results...
            NSLog("search: gathering progress")
        elif notif.name() == NSMetadataQueryDidUpdateNotification:
            # There's a new result available
            NSLog("search: an update happened.")
            self.process_screenshot(notif)


def detect_text(img_path: str, orientation: Optional[int] = None) -> List:
    """process image at img_path with VNRecognizeTextRequest and return list of results

    This code is borrowed from https://github.com/RhetTbull/osxphotos

    Args:
        img_path: path to the image file
        orientation: optional EXIF orientation (if known, passing orientation may improve quality of results)
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
            print(f"Error! {error}")
        else:
            observations = request.results()
            for text_observation in observations:
                recognized_text = text_observation.topCandidates_(1)[0]
                results.append([recognized_text.string(), recognized_text.confidence()])

    return handler


if __name__ == "__main__":
    Textinator(name=APP_NAME, quit_button=None).run()
