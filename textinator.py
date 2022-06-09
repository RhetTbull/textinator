"""Simple MacOS status bar app automatically perform text detection on screenshots.

Runs on Catalina (10.15) and later.
"""

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


ICON = "icon.png"
DEFAULT_CONFIDENCE = 0.5


class Textinator(rumps.App):
    def __init__(self, *args, **kwargs):
        super(Textinator, self).__init__(*args, **kwargs)

        self.icon = ICON
        self.append = rumps.MenuItem("Append to Clipboard", callback=self.on_append)
        self.confidence = rumps.MenuItem(
            f"Text Detection Confidence Threshold: {DEFAULT_CONFIDENCE}"
        )
        self.confidence_slider = rumps.SliderMenuItem(
            value=DEFAULT_CONFIDENCE,
            min_value=0,
            max_value=1,
            callback=self.on_confidence,
        )
        self.quit = rumps.MenuItem("Quit Textinator", callback=self.on_quit)
        self.menu = [self.append, self.confidence, self.confidence_slider, self.quit]

        # append to Clipboard
        self.append.state = False

        # holds all screenshots already seen
        self._screenshots = {}

        # confidence threshold for text detection
        self.confidence_threshold = DEFAULT_CONFIDENCE

        # Start the query
        self.start_query()

    def on_append(self, sender):
        """Toggle append to clipboard."""
        self.append.state = not self.append.state

    def on_confidence(self, sender):
        """Change confidence threshold."""
        self.confidence.title = (
            f"Text detection confidence threshold: {sender.value:.1f}"
        )
        self.confidence_threshold = sender.value

    def start_query(self):
        """Start the NSMetdataQuery Spotlight query."""
        self.query = NSMetadataQuery.alloc().init()
        self.query.setPredicate_(
            NSPredicate.predicateWithFormat_("kMDItemIsScreenCapture = 1")
        )

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
            self._screenshots[path] = text

    def queryUpdated_(self, notif):
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
    Textinator(name="Textinator", quit_button=None).run()
