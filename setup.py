"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup

APP = ["textinator.py"]
DATA_FILES = ["icon.png"]
OPTIONS = {
    "iconfile": "icon.icns",
    "plist": {"LSUIElement": True},
}

setup(
    app=APP,
    data_files=DATA_FILES,
    name="Textinator",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
