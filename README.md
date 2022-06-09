# ChargeMon

Simple macOS StatusBar app to monitor battery charge status and remind you to unplug your Mac when the battery is sufficiently charged

# Overview

Very simple app -- can toggle between alert or notification.  No other settings.

![StatusBar screenshot](statusbar.png)

Sample alert:

![Alert screenshot](alert.png)

## Installation

- clone the repo
- cd into the repo directory
- create a virtual environment and activate it
- python3 -m pip install -r requirements.txt
- python3 setup.py py2app
- Copy dist/chargemon.app to /Applications

## Notes

Doesn't work with python 3.10 as [rumps](https://github.com/jaredks/rumps) is currently not compatible with 3.10.


If building with [pyenv](https://github.com/pyenv/pyenv) installed python, you'll need to build the python with framework support: 

`env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install -v 3.9.11`

## Credits

Inspired by this [tweet](https://twitter.com/mathsppblog/status/1462706686058246151) by [@mathsppblog](https://twitter.com/mathsppblog).

## License

MIT License

# See Also

[iBatteryStats](https://github.com/saket13/iBatteryStats) - a similar idea with many more features
