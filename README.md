# Textinator

Simple macOS StatusBar / menu bar app to perform automatic text detection on screenshots.

## Overview

Install the app per [instructions](#installation) below.  Then, take a screenshot of a region of the screen using ⌘ + ⇧ + 4 (`Cmd + Shift + 4`).  The app will automatically detect any text in the screenshot and copy it to your clipboard.

[![Watch the screencast](https://img.youtube.com/vi/K_3MXOeBBdY/maxresdefault.jpg)](https://youtu.be/K_3MXOeBBdY)

## Installation

- clone the repo
- cd into the repo directory
- create a virtual environment and activate it
- python3 -m pip install -r requirements.txt
- python3 setup.py py2app
- Copy dist/textinator.app to /Applications
- Open System Preferences > Security & Privacy > Full Disk Access 
- Click the padlock if locked to unlock it and add Textinator to the list of allowed apps

![System Preferences > Security & Privacy](images/Full_Disk_Access.png)

- Launch Textinator from the Applications folder
- Click the menu bar icon to see preferences

![Menu Bar Icon](images/textinator_settings.png)

- Press ⌘ + ⇧ + 4 (`Cmd + Shift + 4`) to take a screenshot then paste the detected text wherever you'd like it to be.

## Inspiration

I heard [mikeckennedy](https://github.com/mikeckennedy) mention [Text Sniper](https://textsniper.app/) on [Python Bytes](https://pythonbytes.fm/) podcast [#284](https://pythonbytes.fm/episodes/show/284/spicy-git-for-engineers) and thought "That's neat! I bet I could make a clone in Python!" and here it is.  You should listen to Python Bytes if you don't already and you should go buy Text Sniper!

## Notes

* Doesn't work with python 3.10 as [rumps](https://github.com/jaredks/rumps) is currently not compatible with 3.10.
* If building with [pyenv](https://github.com/pyenv/pyenv) installed python, you'll need to build the python with framework support:
    * `env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install -v 3.9.11`

## License

MIT License

## See Also

[Text Sniper](https://textsniper.app/) - You should buy this!
