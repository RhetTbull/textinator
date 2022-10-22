"""Use macOS Vision API to detect text and QR codes in images"""

from typing import List, Optional, Tuple

import objc
import Quartz
import Vision
from Foundation import NSURL, NSDictionary, NSLog

from utils import get_mac_os_version

__all__ = [
    "ciiimage_from_file",
    "detect_qrcodes_in_ciimage",
    "detect_qrcodes_in_file",
    "detect_text_in_ciimage",
    "detect_text_in_file",
    "get_supported_vision_languages",
]


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


def ciimage_from_file(filepath: str) -> Quartz.CIImage:
    """Create a Quartz.CIImage from a file

    Args:
        filepath: path to the image file

    Returns:
        Quartz.CIImage
    """
    with objc.autorelease_pool():
        input_url = NSURL.fileURLWithPath_(filepath)
        return Quartz.CIImage.imageWithContentsOfURL_(input_url)


def detect_text_in_file(
    img_path: str,
    orientation: Optional[int] = None,
    languages: Optional[List[str]] = None,
) -> List[Tuple[str, float]]:
    """process image file at img_path with VNRecognizeTextRequest and return list of results

    Args:
        img_path: path to the image file
        orientation: optional EXIF orientation (if known, passing orientation may improve quality of results)
        languages: optional languages to use for text detection as list of ISO language code strings; default is ["en-US"]

    Returns:
        List of results where each result is a list of [text, confidence]
    """
    input_image = ciimage_from_file(img_path)
    return detect_text_in_ciimage(input_image, orientation, languages)


def detect_text_in_ciimage(
    image: Quartz.CIImage,
    orientation: Optional[int] = None,
    languages: Optional[List[str]] = None,
) -> List[Tuple[str, float]]:
    """process CIImage with VNRecognizeTextRequest and return list of results

    This code originally developed for https://github.com/RhetTbull/osxphotos

    Args:
        image: CIIImage to process
        orientation: optional EXIF orientation (if known, passing orientation may improve quality of results)
        languages: optional languages to use for text detection as list of ISO language code strings; default is ["en-US"]

    Returns:
        List of results where each result is a list of [text, confidence]
    """
    with objc.autorelease_pool():
        vision_options = NSDictionary.dictionaryWithDictionary_({})
        if orientation is None:
            vision_handler = (
                Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
                    image, vision_options
                )
            )
        elif 1 <= orientation <= 8:
            vision_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_orientation_options_(
                image, orientation, vision_options
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

        return [(str(result[0]), float(result[1])) for result in results]


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


def detect_qrcodes_in_file(img_path: str) -> List[str]:
    """Detect QR Codes in image files using CIDetector and return text of the found QR Codes

    Args:
        img_path: path to the image file

    Returns:
        List of QR Code payload texts found in the image
    """

    input_image = ciimage_from_file(img_path)
    return detect_qrcodes_in_ciimage(input_image)


def detect_qrcodes_in_ciimage(image: Quartz.CIImage) -> List[str]:
    """Detect QR Codes in image using CIDetector and return text of the found QR Codes

    Args:
        input_image: CIImage to process

    Returns:
        List of QR Code payload texts found in the image
    """

    with objc.autorelease_pool():
        context = Quartz.CIContext.contextWithOptions_(None)
        options = NSDictionary.dictionaryWithDictionary_(
            {"CIDetectorAccuracy": Quartz.CIDetectorAccuracyHigh}
        )
        detector = Quartz.CIDetector.detectorOfType_context_options_(
            Quartz.CIDetectorTypeQRCode, context, options
        )

        results = []
        features = detector.featuresInImage_(image)

        if not features:
            return []
        for idx in range(features.count()):
            feature = features.objectAtIndex_(idx)
            results.append(feature.messageString())
        return results
