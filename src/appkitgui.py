"""Toolkit to help create a native macOS GUI with AppKit

Copyright (c) 2023, Rhet Turnbull; licensed under MIT License.
"""

from __future__ import annotations

import datetime
import os
import zoneinfo
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable

import AppKit
from AppKit import (
    NSApp,
    NSBox,
    NSButton,
    NSComboBox,
    NSDatePicker,
    NSImageView,
    NSScrollView,
    NSStackView,
    NSTextField,
    NSTextView,
    NSTimeZone,
    NSView,
)
from Foundation import NSURL, NSDate, NSLog, NSMakeRect, NSMakeSize, NSObject
from objc import objc_method, python_method, super

################################################################################
# Constants
################################################################################

# margin between window edge and content
EDGE_INSET = 20

# padding between elements
PADDING = 8


################################################################################
# Window and Application
################################################################################


def window(
    title: str | None = None,
    size: tuple[int, int] = (600, 600),
    mask: int = AppKit.NSWindowStyleMaskTitled
    | AppKit.NSWindowStyleMaskClosable
    | AppKit.NSWindowStyleMaskResizable,
) -> AppKit.NSWindow:
    """Create a window with a title and size"""
    new_window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, *size),
        mask,
        AppKit.NSBackingStoreBuffered,
        False,
    )
    new_window.center()
    if title is not None:
        new_window.setTitle_(title)
    return new_window


def main_view(
    window: AppKit.NSWindow,
    align: int = AppKit.NSLayoutAttributeLeft,
    padding: int = PADDING,
    edge_inset: tuple[float, float, float, float] | float = EDGE_INSET,
) -> AppKit.NSView:
    """Create a main NSStackView for the window which contains all other views

    Args:
        window: the NSWindow to attach the view to
        align: NSLayoutAttribute alignment constant
        padding: padding between elements
        edge_inset: The geometric padding, in points, inside the stack view, surrounding its views (NSEdgeInsets)
    """

    # This uses appkitgui.StackView which is a subclass of NSStackView
    # that supports some list methods such as append, extend, remove, ...
    main_view = StackView.stackViewWithViews_(None)
    main_view.setOrientation_(AppKit.NSUserInterfaceLayoutOrientationVertical)
    main_view.setSpacing_(padding)
    if isinstance(edge_inset, (int, float)):
        # use even insets
        edge_insets = (edge_inset, edge_inset, edge_inset, edge_inset)
    else:
        edge_insets = edge_inset
    main_view.setEdgeInsets_(edge_insets)
    main_view.setDistribution_(AppKit.NSStackViewDistributionFill)
    main_view.setAlignment_(align)

    window.contentView().addSubview_(main_view)
    top_constraint = main_view.topAnchor().constraintEqualToAnchor_(
        main_view.superview().topAnchor()
    )
    top_constraint.setActive_(True)
    bottom_constraint = main_view.bottomAnchor().constraintEqualToAnchor_(
        main_view.superview().bottomAnchor()
    )
    bottom_constraint.setActive_(True)
    left_constraint = main_view.leftAnchor().constraintEqualToAnchor_(
        main_view.superview().leftAnchor()
    )
    left_constraint.setActive_(True)
    right_constraint = main_view.rightAnchor().constraintEqualToAnchor_(
        main_view.superview().rightAnchor()
    )
    right_constraint.setActive_(True)

    return main_view


################################################################################
# Custom views and control classes
################################################################################


class StackView(NSStackView):
    """NSStackView that supports list methods for adding child views"""

    @python_method
    def append(self, view: NSView):
        """Add view to stack"""
        self.addArrangedSubview_(view)

    @python_method
    def extend(self, views: Iterable[NSView]):
        """Extend stack with the contents of views"""
        for view in views:
            self.append(view)

    @python_method
    def insert(self, i: int, view: NSView):
        """Insert view at index i"""
        self.insertArrangedSubview_atIndex_(view, i)

    @python_method
    def remove(self, view: NSView):
        """Remove view from the stack"""
        self.removeArrangedSubview_(view)


class ScrolledStackView(NSScrollView):
    """A scrollable stack view; use self.documentView() or self.stack to access the stack view"""

    def initWithStack_(
        self,
        stack: NSStackView | StackView,
        vscroll: bool = False,
        hscroll: bool = False,
    ):
        self = super().init()
        if not self:
            return

        self.stack: NSStackView | StackView = stack
        self.setHasVerticalScroller_(vscroll)
        self.setHasHorizontalScroller_(hscroll)
        self.setBorderType_(AppKit.NSNoBorder)
        self.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self.setDrawsBackground_(False)
        self.setAutohidesScrollers_(True)

        self.setDocumentView_(self.stack)

        return self

    @python_method
    def append(self, view: NSView):
        """Add view to stack"""
        self.documentView().addArrangedSubview_(view)

    @python_method
    def extend(self, views: Iterable[NSView]):
        """Extend stack with the contents of views"""
        for view in views:
            self.documentView().append(view)

    @python_method
    def insert(self, i: int, view: NSView):
        """Insert view at index i"""
        self.documentView().insertArrangedSubview_atIndex_(view, i)

    @python_method
    def remove(self, view: NSView):
        """Remove view from the stack"""
        self.documentView().removeArrangedSubview_(view)

    def setSpacing_(self, spacing):
        self.stack.setSpacing_(spacing)

    def setOrientation_(self, orientation):
        self.stack.setOrientation_(orientation)

    def setDistribution_(self, distribution):
        self.stack.setDistribution_(distribution)

    def setAlignment_(self, alignment):
        self.stack.setAlignment_(alignment)

    def setEdgeInsets_(self, edge_inset):
        self.stack.setEdgeInsets_(edge_inset)


class LinkLabel(NSTextField):
    """Uneditable text field that displays a clickable link"""

    def initWithText_URL_(self, text: str, url: str):
        self = super().init()

        if not self:
            return

        attr_str = self.attributedStringWithLinkToURL_text_(url, text)
        self.setAttributedStringValue_(attr_str)
        self.url = NSURL.URLWithString_(url)
        self.setBordered_(False)
        self.setSelectable_(False)
        self.setEditable_(False)
        self.setBezeled_(False)
        self.setDrawsBackground_(False)

        return self

    def resetCursorRects(self):
        self.addCursorRect_cursor_(self.bounds(), AppKit.NSCursor.pointingHandCursor())

    def mouseDown_(self, event):
        AppKit.NSWorkspace.sharedWorkspace().openURL_(self.url)

    def mouseEntered_(self, event):
        AppKit.NSCursor.pointingHandCursor().push()

    def mouseExited_(self, event):
        AppKit.NSCursor.pop()

    def attributedStringWithLinkToURL_text_(self, url: str, text: str):
        linkAttributes = {
            AppKit.NSLinkAttributeName: NSURL.URLWithString_(url),
            AppKit.NSUnderlineStyleAttributeName: AppKit.NSUnderlineStyleSingle,
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.linkColor(),
            # AppKit.NSCursorAttributeName: AppKit.NSCursor.pointingHandCursor(),
        }
        return AppKit.NSAttributedString.alloc().initWithString_attributes_(
            text, linkAttributes
        )


class ComboBoxDelegate(NSObject):
    """Helper class to handle combo box events"""

    def initWithTarget_Action_(self, target: NSObject, action: Callable | str | None):
        self = super().init()
        if not self:
            return

        self.target = target
        self.action_change = action
        return self

    @objc_method
    def comboBoxSelectionDidChange_(self, notification):
        if self.action_change:
            if type(self.action_change) == str:
                self.target.performSelector_withObject_(
                    self.action_change, notification.object()
                )
            else:
                self.action_change(notification.object())


class ComboBox(NSComboBox):
    """NSComboBox that stores a reference to its delegate

    Note:
        This is required to maintain a reference to the delegate, otherwise it will
        not be retained after the ComboBox is created.
    """

    def setDelegate_(self, delegate: NSObject | None):
        self.delegate = delegate
        if delegate is not None:
            super().setDelegate_(delegate)


class ScrollViewWithTextView(NSScrollView):
    def initWithSize_VScroll_(self, size: tuple[float, float], vscroll: bool):
        self = super().initWithFrame_(NSMakeRect(0, 0, *size))
        if not self:
            return
        self.setBorderType_(AppKit.NSBezelBorder)
        self.setHasVerticalScroller_(vscroll)
        self.setDrawsBackground_(True)
        self.setAutohidesScrollers_(True)
        self.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )
        self.setTranslatesAutoresizingMaskIntoConstraints_(False)

        width_constraint = self.widthAnchor().constraintEqualToConstant_(size[0])
        width_constraint.setActive_(True)
        height_constraint = self.heightAnchor().constraintEqualToConstant_(size[1])
        height_constraint.setActive_(True)

        contentSize = self.contentSize()
        self.textView = NSTextView.alloc().initWithFrame_(self.contentView().frame())
        self.textView.setMinSize_(NSMakeSize(0.0, contentSize.height))
        self.textView.setMaxSize_(NSMakeSize(float("inf"), float("inf")))
        self.textView.setVerticallyResizable_(True)
        self.textView.setHorizontallyResizable_(False)
        self.setDocumentView_(self.textView)

        return self

    # provide access to some of the text view's methods
    def string(self):
        return self.textView.string()

    def setString_(self, text: str):
        self.textView.setString_(text)

    def setEditable_(self, editable: bool):
        self.textView.setEditable_(editable)

    def setSelectable_(self, selectable: bool):
        self.textView.setSelectable_(selectable)

    def setFont_(self, font: AppKit.NSFont):
        self.textView.setFont_(font)

    def setTextColor_(self, color: AppKit.NSColor):
        self.textView.setTextColor_(color)

    def setBackgroundColor_(self, color: AppKit.NSColor):
        self.textView.setBackgroundColor_(color)


################################################################################
# Helper functions to create views and controls
################################################################################


def hstack(
    align: int = AppKit.NSLayoutAttributeTop,
    distribute: int | None = AppKit.NSStackViewDistributionFill,
    vscroll: bool = False,
    hscroll: bool = False,
    views: (
        Iterable[AppKit.NSView] | AppKit.NSArray | AppKit.NSMutableArray | None
    ) = None,
    edge_inset: tuple[float, float, float, float] | float = 0,
) -> StackView:
    """Create a horizontal StackView

    Args:
        align:NSLayoutAttribute alignment constant
        distribute: NSStackViewDistribution distrubution constant
        vscroll: True to add vertical scrollbar
        hscroll: True to add horizontal scrollbar
        views: iterable of NSViews to add to the stack
        edge_inset: The geometric padding, in points, inside the stack view, surrounding its views (NSEdgeInsets)

    Returns: StackView
    """
    hstack = StackView.stackViewWithViews_(views)
    hstack.setSpacing_(PADDING)
    hstack.setOrientation_(AppKit.NSUserInterfaceLayoutOrientationHorizontal)
    if distribute is not None:
        hstack.setDistribution_(distribute)
    hstack.setAlignment_(align)
    hstack.setTranslatesAutoresizingMaskIntoConstraints_(False)
    hstack.setHuggingPriority_forOrientation_(
        AppKit.NSLayoutPriorityDefaultHigh,
        AppKit.NSLayoutConstraintOrientationHorizontal,
    )
    if edge_inset:
        if isinstance(edge_inset, (int, float)):
            # use even insets
            edge_insets = (edge_inset, edge_inset, edge_inset, edge_inset)
        else:
            edge_insets = edge_inset
        hstack.setEdgeInsets_(edge_insets)
    if vscroll or hscroll:
        scroll_view = ScrolledStackView.alloc().initWithStack_(hstack, vscroll, hscroll)
        return scroll_view
    return hstack


def vstack(
    align: int = AppKit.NSLayoutAttributeLeft,
    distribute: int | None = None,
    vscroll: bool = False,
    hscroll: bool = False,
    views: AppKit.NSArray | AppKit.NSMutableArray | None = None,
    edge_inset: tuple[float, float, float, float] | float = 0,
) -> StackView | ScrolledStackView:
    """Create a vertical StackView

    Args:
        align:NSLayoutAttribute alignment constant
        distribute: NSStackViewDistribution distrubution constant
        vscroll: True to add vertical scrollbar
        hscroll: True to add horizontal scrollbar
        views: iterable of NSViews to add to the stack
        edge_inset: The geometric padding, in points, inside the stack view, surrounding its views (NSEdgeInsets)

    Returns: StackView
    """
    vstack = StackView.stackViewWithViews_(views)
    vstack.setSpacing_(PADDING)
    vstack.setOrientation_(AppKit.NSUserInterfaceLayoutOrientationVertical)
    if distribute is not None:
        vstack.setDistribution_(distribute)
    vstack.setAlignment_(align)
    vstack.setTranslatesAutoresizingMaskIntoConstraints_(False)
    # TODO: set priority as arg? or let user set it later?
    vstack.setHuggingPriority_forOrientation_(
        AppKit.NSLayoutPriorityDefaultHigh,
        AppKit.NSLayoutConstraintOrientationVertical,
    )
    if edge_inset:
        if isinstance(edge_inset, (int, float)):
            # use even insets
            edge_insets = (edge_inset, edge_inset, edge_inset, edge_inset)
        else:
            edge_insets = edge_inset
        vstack.setEdgeInsets_(edge_insets)

    if vscroll or hscroll:
        scroll_view = ScrolledStackView.alloc().initWithStack_(vstack, vscroll, hscroll)
        return scroll_view
    return vstack


def hspacer() -> NSStackView:
    """Create a horizontal spacer"""
    return vstack()


def label(value: str) -> NSTextField:
    """Create a label"""
    label = NSTextField.labelWithString_(value)
    label.setEditable_(False)
    label.setBordered_(False)
    label.setBackgroundColor_(AppKit.NSColor.clearColor())
    return label


def link(text: str, url: str) -> NSTextField:
    """Create a clickable link label"""
    return LinkLabel.alloc().initWithText_URL_(text, url)


def button(title: str, target: NSObject, action: Callable | str | None) -> NSButton:
    """Create a button"""
    button = NSButton.buttonWithTitle_target_action_(title, target, action)
    button.setTranslatesAutoresizingMaskIntoConstraints_(False)

    # set hugging priority and compression resistance to prevent button from resizing
    set_hugging_priority(button)
    set_compression_resistance(button)

    return button


def checkbox(title: str, target: NSObject, action: Callable | str | None) -> NSButton:
    """Create a checkbox button"""
    checkbox = NSButton.buttonWithTitle_target_action_(title, target, action)
    checkbox.setButtonType_(AppKit.NSButtonTypeSwitch)  # Switch button type
    return checkbox


def radio_button(
    title: str, target: NSObject, action: Callable | str | None
) -> NSButton:
    """Create a radio button"""
    radio_button = NSButton.buttonWithTitle_target_action_(title, target, action)
    radio_button.setButtonType_(AppKit.NSRadioButton)
    return radio_button


def combo_box(
    values: list[str] | None,
    target: NSObject,
    editable: bool = False,
    action_return: Callable | str | None = None,
    action_change: Callable | str | None = None,
    delegate: NSObject | None = None,
    width: float | None = None,
) -> NSComboBox:
    """Create a combo box

    Args:
        values: list of values to populate the combo box with
        target: target to send action to
        editable: whether the combo box is editable
        action_return: action to send when return is pressed (only called if editable is True)
        action_change: action to send when the selection is changed
        delegate: delegate to handle events; if not provided a default delegate is automatically created
        width: width of the combo box; if None, the combo box will resize to the contents


    Note:
        In order to handle certain events such as return being pressed, a delegate is
        required. If a delegate is not provided, a default delegate is automatically
        created which will call the action_return callback when return is pressed.
        If a delegate is provided, it may implement the following methods:

                - comboBoxSelectionDidChange
                - comboBox_textView_doCommandBySelector
    """

    combo_box = ComboBox.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 25))
    combo_box.setTarget_(target)
    delegate = delegate or ComboBoxDelegate.alloc().initWithTarget_Action_(
        target, action_change
    )
    combo_box.setDelegate_(delegate)
    if values:
        combo_box.addItemsWithObjectValues_(values)
        combo_box.selectItemAtIndex_(0)
    if action_return:
        combo_box.setAction_(action_return)
    combo_box.setCompletes_(True)
    combo_box.setEditable_(editable)

    if width is not None:
        constrain_to_width(combo_box, width)
    return combo_box


def hseparator() -> NSBox:
    """Create a horizontal separator"""
    separator = NSBox.alloc().init()
    separator.setBoxType_(AppKit.NSBoxSeparator)
    separator.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return separator


def image_view(
    path: str | os.PathLike,
    width: int | None = None,
    height: int | None = None,
    scale: int = AppKit.NSImageScaleProportionallyUpOrDown,
    align: int = AppKit.NSImageAlignCenter,
) -> NSImageView:
    """Create an image view from a an image file.

    Args:
        path: path to the image file
        width: width to constrain the image to; if None, the image will not be constrained
        height: height to constrain the image to; if None, the image will not be constrained
        scale: scaling mode for the image
        align: alignment mode for the image

    Returns: NSImageView

    Note: if only one of width or height set, the other will be scaled to maintain aspect ratio.
    If image is smaller than the specified width or height and scale is set to AppKit.NSImageScaleNone,
    the image frame will be larger than the image and the image will be aligned according to align.
    """
    image = AppKit.NSImage.alloc().initByReferencingFile_(str(path))
    image_view = NSImageView.imageViewWithImage_(image)
    image_view.setImageScaling_(scale)
    image_view.setImageAlignment_(align)
    image_view.setTranslatesAutoresizingMaskIntoConstraints_(False)

    # if width or height set, constrain to that size
    # if only one of width or height is set, constrain to that size and scale the other to maintain aspect ratio
    # if this is not done, the NSImageView intrinsic size may be larger than the window and thus disrupt the layout

    if width:
        image_view.widthAnchor().constraintEqualToConstant_(width).setActive_(True)
        if not height:
            aspect_ratio = image.size().width / image.size().height
            scaled_height = width / aspect_ratio
            image_view.heightAnchor().constraintEqualToConstant_(
                scaled_height
            ).setActive_(True)
    if height:
        image_view.heightAnchor().constraintEqualToConstant_(height).setActive_(True)
        if not width:
            aspect_ratio = image.size().width / image.size().height
            scaled_width = height * aspect_ratio
            image_view.widthAnchor().constraintEqualToConstant_(
                scaled_width
            ).setActive_(True)

    return image_view


def date_picker(
    style: int = AppKit.NSDatePickerStyleClockAndCalendar,
    elements: int = AppKit.NSDatePickerElementFlagYearMonthDay,
    mode: int = AppKit.NSDatePickerModeSingle,
    date: datetime.date | datetime.datetime | None = None,
    target: NSObject | None = None,
    action: Callable | str | None = None,
    size: tuple[int, int] = (200, 50),
) -> NSDatePicker:
    """Create a date picker

    Args:
        style: style of the date picker, an AppKit.NSDatePickerStyle
        elements: elements to display in the date picker, an AppKit.NSDatePickerElementFlag
        mode: mode of the date picker, an AppKit.NSDatePickerMode
        date: initial date of the date picker; if None, defaults to the current date
        target: target to send action to
        action: action to send when the date is changed
        size: size of the date picker

    Returns: NSDatePicker
    """
    date = date or datetime.date.today()
    date_picker = NSDatePicker.alloc().initWithFrame_(NSMakeRect(0, 0, *size))
    date_picker.setDatePickerStyle_(style)
    date_picker.setDatePickerElements_(elements)
    date_picker.setDatePickerMode_(mode)
    date_picker.setDateValue_(date)
    date_picker.setTimeZone_(NSTimeZone.localTimeZone())
    date_picker.setTranslatesAutoresizingMaskIntoConstraints_(False)

    if target:
        date_picker.setTarget_(target)
    if action:
        date_picker.setAction_(action)
    return date_picker


def time_picker(
    style: int = AppKit.NSDatePickerStyleTextFieldAndStepper,
    elements: int = AppKit.NSDatePickerElementFlagHourMinute,
    mode: int = AppKit.NSDatePickerModeSingle,
    time: datetime.datetime | datetime.time | None = None,
    target: NSObject | None = None,
    action: Callable | str | None = None,
) -> NSDatePicker:
    """Create a time picker

    Args:
        style: style of the date picker, an AppKit.NSDatePickerStyle
        elements: elements to display in the date picker, an AppKit.NSDatePickerElementFlag
        mode: mode of the date picker, an AppKit.NSDatePickerMode
        time: initial time of the date picker; if None, defaults to the current time
        target: target to send action to
        action: action to send when the date is changed

    Returns: NSDatePicker


    Note: This function is a wrapper around date_picker, with the date picker style set to
    display a time picker.
    """
    # if time is only a time, convert to datetime with today's date
    # as the date picker requires a datetime or date
    if isinstance(time, datetime.time):
        time = datetime.datetime.combine(datetime.date.today(), time)
    time = time or datetime.datetime.now()
    return date_picker(
        style=style,
        elements=elements,
        mode=mode,
        date=time,
        target=target,
        action=action,
    )


def text_view(
    size: tuple[float, float] = (400, 100), vscroll: bool = True
) -> NSTextView:
    """Create a text view with optional vertical scroll"""
    return ScrollViewWithTextView.alloc().initWithSize_VScroll_(size, vscroll)


def text_field(
    size: tuple[float, float] = (200, 25),
    placeholder: str | None = None,
    target: NSObject | None = None,
    action: Callable | str | None = None,
) -> NSTextField:
    """Create a text field"""
    text_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, *size))
    text_field.setBezeled_(True)
    text_field.setBezelStyle_(AppKit.NSTextFieldSquareBezel)
    text_field.setTranslatesAutoresizingMaskIntoConstraints_(False)
    width_constraint = text_field.widthAnchor().constraintEqualToConstant_(size[0])
    width_constraint.setActive_(True)
    height_constraint = text_field.heightAnchor().constraintEqualToConstant_(size[1])
    height_constraint.setActive_(True)
    if placeholder:
        text_field.setPlaceholderString_(placeholder)
    if target:
        text_field.setTarget_(target)
    if action:
        text_field.setAction_(action)

    return text_field


################################################################################
# Menus
################################################################################


def menu_bar() -> AppKit.NSMenuItem:
    """Create the app's menu bar"""
    menu = menu_with_submenu(None)
    NSApp.setMainMenu_(menu)
    return menu


def menu_main() -> AppKit.NSMenu:
    """Return app's main menu"""
    return NSApp.mainMenu()


def menu_with_submenu(
    title: str | None = None, parent: AppKit.NSMenu | None = None
) -> AppKit.NSMenu:
    """Create a menu with a submenu"""
    if title:
        menu = AppKit.NSMenu.alloc().initWithTitle_(title)
    else:
        menu = AppKit.NSMenu.alloc().init()
    sub_menu = menu_item(title)
    sub_menu.setSubmenu_(menu)
    if parent:
        parent.addItem_(sub_menu)
    return menu


def menu_item(
    title: str | None,
    parent: AppKit.NSMenu | None = None,
    target: NSObject | None = None,
    action: Callable | str | None = None,
    key: str | None = None,
) -> AppKit.NSMenuItem:
    """Create a menu item and optionally add it to a parent menu"""
    key = key or ""
    title = title or ""
    item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        title, action, key
    )
    if target:
        item.setTarget_(target)
    if parent:
        parent.addItem_(item)
    return item


@dataclass
class MenuItem:
    title: str
    target: NSObject | None = None
    action: Callable | str | None = None
    key: str | None = None


def menus_from_dict(
    menus: dict[str, Iterable[MenuItem | dict]],
    target: NSObject | None = None,
    parent: AppKit.NSMenu | None = None,
) -> dict[str, list[AppKit.NSMenu | dict]]:
    """Create menus from a dict

    Args:
        menus: dict of
        target: the default target object for menu items (for example, window class's self)
        parent: the parent menu; if None, uses the app's top-level menu as parent

    Returns:
        dict of menus and their children

    Note:
        target may be specified in the target argument and will be used as the default target for all menu items
        unless the menu item specifies a different target in the MenuItem.target field.
        .When calling this from your app, leave parent = None to add the menu items to the app's top-level menu
    """
    top_level_menus = {}
    parent = parent or menu_main()
    for title, value in menus.items():
        top_menu = menu_with_submenu(title, parent)
        top_level_menus[title] = [top_menu]
        if isinstance(value, Iterable):
            for item in value:
                if isinstance(item, dict):
                    top_level_menus[title].append(
                        menus_from_dict(item, target, top_menu)
                    )
                else:
                    child_item = menu_item(
                        title=item.title,
                        parent=top_menu,
                        action=item.action,
                        target=item.target or target,
                        key=item.key,
                    )
                    top_level_menus[title].append({item.title: child_item})
    return top_level_menus


################################################################################
# Utility Functions
################################################################################


def min_with_index(values: list[float]) -> tuple[int, int]:
    """Return the minimum value and index of the minimum value in a list"""
    min_value = min(values)
    min_index = values.index(min_value)
    return min_value, min_index


def nsdate_to_datetime(nsdate: NSDate):
    """Convert an NSDate to a datetime in the specified timezone

    Args:
        nsdate: NSDate to convert

    Returns: naive datetime.datetime

    Note: timezone is the identifier of the timezone to convert to, e.g. "America/New_York" or "US/Eastern"
    """
    # NSDate's reference date is 2001-01-01 00:00:00 +0000
    reference_date = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
    seconds_since_ref = nsdate.timeIntervalSinceReferenceDate()
    dt = reference_date + datetime.timedelta(seconds=seconds_since_ref)
    # all NSDates are naive; use local timezone to adjust from UTC to local
    timezone = NSTimeZone.localTimeZone().name()
    try:
        tz = zoneinfo.ZoneInfo(timezone)
    except zoneinfo.ZoneInfoNotFoundError:
        raise ValueError(f"Invalid timezone: {timezone}")

    dt = dt.astimezone(tz=tz)
    return dt.replace(tzinfo=None)


################################################################################
# Constraint helper functions
################################################################################


def set_hugging_priority(
    view: NSView,
    priority: float = AppKit.NSLayoutPriorityDefaultHigh,
    orientation: int = AppKit.NSLayoutConstraintOrientationHorizontal,
):
    """Set content hugging priority for a view"""
    view.setContentHuggingPriority_forOrientation_(
        priority,
        orientation,
    )


def set_compression_resistance(
    view: NSView,
    priority: float = AppKit.NSLayoutPriorityDefaultHigh,
    orientation: int = AppKit.NSLayoutConstraintOrientationHorizontal,
):
    """Set content compression resistance for a view"""
    view.setContentCompressionResistancePriority_forOrientation_(priority, orientation)


def constrain_stacks_side_by_side(
    *stacks: NSStackView,
    weights: list[float] | None = None,
    parent: NSStackView | None = None,
    padding: int = 0,
    edge_inset: float = 0,
):
    """Constrain a list of NSStackViews to be side by side optionally using weighted widths

    Args:
        *stacks: NSStackViews to constrain
        weights: optional weights to use for each stack
        parent: NSStackView to constrain the stacks to; if None, uses stacks[0].superview()
        padding: padding between stacks
        edge_inset: padding between stacks and parent


    Note:
        If weights are provided, the stacks will be constrained to be side by side with
        widths proportional to the weights. For example, if 2 stacks are provided with
        weights = [1, 2], the first stack will be half the width of the second stack.
    """

    if len(stacks) < 2:
        raise ValueError("Must provide at least two stacks")

    parent = parent or stacks[0].superview()

    if weights is not None:
        min_weight, min_index = min_with_index(weights)
    else:
        min_weight, min_index = 1.0, 0

    for i, stack in enumerate(stacks):
        if i == 0:
            stack.leadingAnchor().constraintEqualToAnchor_constant_(
                parent.leadingAnchor(), edge_inset
            ).setActive_(True)
        else:
            stack.leadingAnchor().constraintEqualToAnchor_constant_(
                stacks[i - 1].trailingAnchor(), padding
            ).setActive_(True)
        if i == len(stacks) - 1:
            stack.trailingAnchor().constraintEqualToAnchor_constant_(
                parent.trailingAnchor(), -edge_inset
            ).setActive_(True)
        stack.topAnchor().constraintEqualToAnchor_constant_(
            parent.topAnchor(), edge_inset
        ).setActive_(True)
        stack.bottomAnchor().constraintEqualToAnchor_constant_(
            parent.bottomAnchor(), -edge_inset
        ).setActive_(True)

        if not weights:
            continue

        weight = weights[i] / min_weight

        AppKit.NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            stack,
            AppKit.NSLayoutAttributeWidth,
            AppKit.NSLayoutRelationEqual,
            stacks[min_index],
            AppKit.NSLayoutAttributeWidth,
            weight,
            0.0,
        ).setActive_(
            True
        )


def constrain_stacks_top_to_bottom(
    *stacks: NSStackView,
    weights: list[float] | None = None,
    parent: NSStackView | None = None,
    padding: int = 0,
    edge_inset: float = 0,
):
    """Constrain a list of NSStackViews to be top to bottom optionally using weighted widths

    Args:
        *stacks: NSStackViews to constrain
        weights: optional weights to use for each stack
        parent: NSStackView to constrain the stacks to; if None, uses stacks[0].superview()
        padding: padding between stacks
        edge_inset: padding between stacks and parent


    Note:
        If weights are provided, the stacks will be constrained to be top to bottom with
        widths proportional to the weights. For example, if 2 stacks are provided with
        weights = [1, 2], the first stack will be half the width of the second stack.
    """

    if len(stacks) < 2:
        raise ValueError("Must provide at least two stacks")

    parent = parent or stacks[0].superview()

    if weights is not None:
        min_weight, min_index = min_with_index(weights)
    else:
        min_weight, min_index = 1.0, 0

    for i, stack in enumerate(stacks):
        if i == 0:
            stack.topAnchor().constraintEqualToAnchor_constant_(
                parent.topAnchor(), edge_inset
            ).setActive_(True)
        else:
            stack.topAnchor().constraintEqualToAnchor_constant_(
                stacks[i - 1].bottomAnchor(), padding
            ).setActive_(True)
        if i == len(stacks) - 1:
            stack.bottomAnchor().constraintEqualToAnchor_constant_(
                parent.bottomAnchor(), -edge_inset
            ).setActive_(True)
        stack.leadingAnchor().constraintEqualToAnchor_constant_(
            parent.leadingAnchor(), edge_inset
        ).setActive_(True)
        stack.trailingAnchor().constraintEqualToAnchor_constant_(
            parent.trailingAnchor(), -edge_inset
        ).setActive_(True)

        if not weights:
            continue

        weight = weights[i] / min_weight

        AppKit.NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            stack,
            AppKit.NSLayoutAttributeHeight,
            AppKit.NSLayoutRelationEqual,
            stacks[min_index],
            AppKit.NSLayoutAttributeHeight,
            weight,
            0.0,
        ).setActive_(
            True
        )


def constrain_to_parent_width(
    view: NSView, parent: NSView | None = None, edge_inset: float = 0
):
    """Constrain an NSView to the width of its parent

    Args:
        view: NSView to constrain
        parent: NSView to constrain the control to; if None, uses view.superview()
        edge_inset: margin between control and parent
    """
    parent = parent or view.superview()
    view.rightAnchor().constraintEqualToAnchor_constant_(
        parent.rightAnchor(), -edge_inset
    ).setActive_(True)
    view.leftAnchor().constraintEqualToAnchor_constant_(
        parent.leftAnchor(), edge_inset
    ).setActive_(True)


def constrain_to_width(view: NSView, width: float | None = None):
    """Constrain an NSView to a fixed width

    Args:
        view: NSView to constrain
        width: width to constrain to; if None, does not apply a width constraint
    """
    if width is not None:
        view.widthAnchor().constraintEqualToConstant_(width).setActive_(True)


def constrain_to_height(view: NSView, height: float | None = None):
    """Constrain an NSView to a fixed height

    Args:
        view: NSView to constrain
        height: height to constrain to; if None, does not apply a height constraint
    """
    if height is not None:
        view.heightAnchor().constraintEqualToConstant_(height).setActive_(True)


def constrain_center_x_to_parent(view: NSView, parent: NSView | None = None):
    """Constrain an NSView to the center of its parent along the x-axis

    Args:
        view: NSView to constrain
        parent: NSView to constrain the control to; if None, uses view.superview()
    """
    parent = parent or view.superview()
    view.centerXAnchor().constraintEqualToAnchor_(parent.centerXAnchor()).setActive_(
        True
    )


def constrain_center_y_to_parent(view: NSView, parent: NSView | None = None):
    """Constrain an NSView to the center of its parent along the y-axis

    Args:
        view: NSView to constrain
        parent: NSView to constrain the control to; if None, uses view.superview()
    """
    parent = parent or view.superview()
    view.centerYAnchor().constraintEqualToAnchor_(parent.centerYAnchor()).setActive_(
        True
    )


def constrain_trailing_anchor_to_parent(
    view: NSView, parent: NSView | None = None, edge_inset: float = EDGE_INSET
):
    """Constrain an NSView's trailing anchor to it's parent

    Args:
        view: NSView to constrain
        parent: NSView to constrain the control to; if None, uses view.superview()
        inset: inset from trailing edge to apply to constraint (inset will be subtracted from trailing edge)
    """
    parent = parent or view.superview()
    view.trailingAnchor().constraintEqualToAnchor_constant_(
        parent.trailingAnchor(), -edge_inset
    ).setActive_(True)
