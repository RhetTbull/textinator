"""Simple MacOS status bar app automatically perform text detection on screenshots.

Runs on Catalina (10.15) and later.
"""

import pyperclip
import rumps
from Foundation import (
    NSLog,
    NSMetadataQuery,
    NSMetadataQueryDidFinishGatheringNotification,
    NSMetadataQueryDidStartGatheringNotification,
    NSMetadataQueryDidUpdateNotification,
    NSMetadataQueryGatheringProgressNotification,
    NSNotificationCenter,
    NSPredicate,
)

from .text_detection import detect_text

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


if __name__ == "__main__":
    Textinator(name="Textinator", quit_button=None).run()
