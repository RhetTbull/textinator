"""Tests for Textinator"""

import os
from time import sleep

from .conftest import (
    click_menu_item,
    click_window_button,
    copy_to_desktop,
    log_file,
    mark_screenshot,
    process_is_running,
)
from .loginitems import list_login_items, remove_login_item

TEST_FILE_HELLO_WORLD = "tests/data/hello_world.png"
TEST_FILE_HELLO_WORLD_LINEBREAK = "tests/data/hello_world_linebreaks.png"
TEST_FILE_HELLO = "tests/data/hello.png"
TEST_FILE_WORLD = "tests/data/world.png"
TEST_QRCODE = "tests/data/qrcode.png"
TEST_QRCODE_WITH_TEXT = "tests/data/qrcode_with_text.png"


def test_screenshot_basic(pb):
    """Test screenshot detection"""
    pb.clear()
    with log_file() as log:
        with copy_to_desktop(TEST_FILE_HELLO_WORLD) as filepath:
            mark_screenshot(filepath)
            sleep(5)
            assert pb.get_text() == "Hello World"
        assert "notification: Processed Screenshot" in log.read()


def test_screenshot_linebreak(pb):
    """Test screenshot detection with linebreaks"""
    pb.clear()
    with log_file() as log:
        with copy_to_desktop(TEST_FILE_HELLO_WORLD_LINEBREAK) as filepath:
            mark_screenshot(filepath)
            sleep(5)
            assert pb.get_text() == "Hello\nWorld"
        assert "notification: Processed Screenshot" in log.read()


def test_screenshot_no_notification(pb):
    """Test screenshot detection with no notification"""
    assert click_menu_item("Notification")
    pb.clear()
    with log_file() as log:
        with copy_to_desktop(TEST_FILE_HELLO_WORLD) as filepath:
            mark_screenshot(filepath)
            sleep(5)
            assert pb.get_text() == "Hello World"
        assert "notification:" not in log.read()
    # turn notification back on
    assert click_menu_item("Notification")


def test_screenshot_append(pb):
    """Test screenshot detection with append"""
    assert click_menu_item("Append to clipboard")
    pb.clear()
    with copy_to_desktop(TEST_FILE_HELLO) as filepath:
        mark_screenshot(filepath)
        sleep(5)
        with copy_to_desktop(TEST_FILE_WORLD) as filepath:
            mark_screenshot(filepath)
            sleep(5)
            assert pb.get_text() == "Hello\nWorld"
    # turn append off
    assert click_menu_item("Append to clipboard")


def test_screenshot_qrcode(pb):
    """Test screenshot detection with QR code"""
    assert click_menu_item("Detect QR codes")
    # set confidence to high because sometimes the QR code is detected as text
    assert click_menu_item("Text detection confidence threshold", "High")
    pb.clear()
    with copy_to_desktop(TEST_QRCODE) as filepath:
        mark_screenshot(filepath)
        sleep(5)
        assert pb.get_text() == "https://github.com/RhetTbull/textinator"
    assert click_menu_item("Detect QR codes")
    assert click_menu_item("Text detection confidence threshold", "Low")


def test_screenshot_qrcode_with_text(pb):
    """Test screenshot detection with QR code and text"""
    assert click_menu_item("Detect QR codes")
    pb.clear()
    with copy_to_desktop(TEST_QRCODE_WITH_TEXT) as filepath:
        mark_screenshot(filepath)
        sleep(5)
        text = pb.get_text()
        assert "https://github.com/RhetTbull/textinator" in text
        assert "SCAN ME" in text
    assert click_menu_item("Detect QR codes")


def test_screenshot_qrcode_with_text_no_detect(pb):
    """Test screenshot detection with QR code and text when QR code detection is off"""
    pb.clear()
    with copy_to_desktop(TEST_QRCODE_WITH_TEXT) as filepath:
        mark_screenshot(filepath)
        sleep(5)
        text = pb.get_text()
        assert "https://github.com/RhetTbull/textinator" not in text
        assert "SCAN ME" in text


def test_pause(pb):
    """Test pause"""
    pb.clear()
    pb.set_text("Paused")
    assert click_menu_item("Pause text detection")
    with log_file() as log:
        with copy_to_desktop(TEST_FILE_HELLO_WORLD) as filepath:
            mark_screenshot(filepath)
            sleep(5)
            assert pb.get_text() == "Paused"
        assert "skipping screenshot because app is paused:" in log.read()
    with log_file() as log:
        assert click_menu_item("Resume text detection")
        with copy_to_desktop(TEST_FILE_HELLO_WORLD) as filepath:
            mark_screenshot(filepath)
            sleep(5)
            assert pb.get_text() == "Hello World"
        assert "notification: Processed Screenshot" in log.read()


def test_confidence(pb):
    """Test text detection confidence menu"""
    pb.clear()
    with log_file() as log:
        assert click_menu_item("Text detection confidence threshold", "Medium")
        sleep(5)
        assert "'confidence': 'MEDIUM'" in log.read()
        with copy_to_desktop(TEST_FILE_HELLO_WORLD) as filepath:
            mark_screenshot(filepath)
            sleep(5)
            assert pb.get_text() == "Hello World"
        assert click_menu_item("Text detection confidence threshold", "Low")
        sleep(5)
        assert "'confidence': 'LOW'" in log.read()


def test_clipboard_basic(pb):
    """Test clipboard detection"""
    pb.clear()
    pb.set_image(TEST_FILE_HELLO_WORLD, "PNG")
    sleep(5)
    assert pb.get_text() == "Hello World"


def test_clipboard_text_and_image(pb):
    """Test clipboard detection when clipboard has text and image (#16)"""
    pb.clear()
    with log_file() as log:
        pb.set_text_and_image("Alt Text", TEST_FILE_HELLO_WORLD, "PNG")
        sleep(5)
        assert "clipboard has text, skipping" in log.read()
        assert pb.get_text() == "Alt Text"


def test_clipboard_no_clipboard(pb):
    """Test clipboard detection does not run when "Detect text in images on clipboard" is off"""
    assert click_menu_item("Detect text in images on clipboard")
    pb.clear()
    pb.set_image(TEST_FILE_HELLO_WORLD, "PNG")
    sleep(5)
    assert pb.get_text() == ""
    assert click_menu_item("Detect text in images on clipboard")


def test_clear_clipboard(pb):
    """Test Clear clipboard menu item works"""
    pb.set_text("Hello World")
    assert click_menu_item("Clear clipboard")
    sleep(5)
    assert pb.get_text() == ""


def test_confirm_clipboard_changes_yes(pb):
    """Test Confirm clipboard changes menu item works when pressing Yes"""
    pb.clear()
    with log_file() as log:
        assert click_menu_item("Confirm clipboard changes")
        sleep(5)
        assert "'confirmation': 1" in log.read()
    with copy_to_desktop(TEST_FILE_HELLO_WORLD) as filepath:
        mark_screenshot(filepath)
        sleep(5)
        assert click_window_button(1, 1)  # button 1 is Yes
        sleep(5)
        assert pb.get_text() == "Hello World"
    assert click_menu_item("Confirm clipboard changes")


def test_confirm_clipboard_changes_no(pb):
    """Test Confirm clipboard changes menu item works when pressing No"""
    pb.set_text("Nope")
    with log_file() as log:
        assert click_menu_item("Confirm clipboard changes")
        sleep(5)
        assert "'confirmation': 1" in log.read()
    with copy_to_desktop(TEST_FILE_HELLO_WORLD) as filepath:
        mark_screenshot(filepath)
        sleep(5)
        assert click_window_button(1, 2)  # button 2 is "No"
        sleep(5)
        assert pb.get_text() == "Nope"
    assert click_menu_item("Confirm clipboard changes")


def test_enable_start_on_login():
    """Test Start Textinator on login menu item works"""
    # setup_teardown() should have removed the login item if it existed
    assert "Textinator" not in list_login_items()
    assert click_menu_item("Start Textinator on login")
    sleep(5)
    assert "Textinator" in list_login_items()
    assert click_menu_item("Start Textinator on login")
    sleep(5)
    assert "Textinator" not in list_login_items()


def test_about():
    """Test About dialog"""
    assert click_menu_item("About Textinator")
    assert click_window_button(1, 1)


def test_quit():
    """Test Quit menu item"""
    assert process_is_running("Textinator")
    assert click_menu_item("Quit Textinator")
    sleep(5)
    assert not process_is_running("Textinator")
    os.system("open -a Textinator")
