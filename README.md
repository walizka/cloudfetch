# cloudfetch

A clean, lightweight and fast system information fetch written in Python.

cloudfetch displays useful system information directly in your terminal with a custom cloud-themed design.

## Features

* Cloud-themed ASCII logo
* OS detection
* Kernel information
* CPU detection
* Dynamic GPU detection
* RAM usage
* Shell detection
* Window manager detection
* X11 and Wayland support
* Multiple GPU support
* No external Python packages required
* Lightweight and fast
* Cyan, blue and purple terminal aesthetic

## Installation

Download install.sh from the latest release.

Open a terminal in the directory containing install.sh and run:

bash install.sh

The installer automatically detects your shell and configures cloudfetch.

Supported shells:

* Bash
* Zsh
* Fish

After installation, use:

cf

or:

cloudfetch

## Manual Installation

Alternatively, if your shell isn't supported, you can install cloudfetch manually.

Download cf.py from the repository and place it in:

~/.cloudfetch/cf.py

Then make it executable:

chmod +x ~/.cloudfetch/cf.py

You can run cloudfetch manually with:

python3 ~/.cloudfetch/cf.py

If you want to use the cf or cloudfetch commands, add an alias to your shell configuration file.

For example, in Bash:

alias cf='python3 ~/.cloudfetch/cf.py'
alias cloudfetch='python3 ~/.cloudfetch/cf.py'

Then reload your shell configuration and run:

cf

## Requirements

* Linux
* Python 3
* curl or wget

## License

MIT License
