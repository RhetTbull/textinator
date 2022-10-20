"""Use macOS Vision API to detect text and QR codes in images"""

from typing import List, Optional, Tuple

import objc
import Quartz
import Vision
from Foundation import NSURL, NSDictionary, NSLog

from utils import get_mac_os_version

__all__ = ["detect_text", "detect_qrcodes", "get_supported_vision_languages"]


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
            NSLog(f"Error! {error}")
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
