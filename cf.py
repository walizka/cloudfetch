#!/usr/bin/env python3

import base64
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


# ============================================================
# Configuration
# ============================================================

REPO = "https://github.com/walizka/cloudfetch"
GITHUB_API = "https://api.github.com/repos/walizka/cloudfetch/contents/version?ref=main"

INSTALL_DIR = os.path.expanduser("~/.cloudfetch")
VERSION_FILE = os.path.join(INSTALL_DIR, "version")

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[38;5;117m"
BLUE = "\033[38;5;111m"
PURPLE = "\033[38;5;183m"
WHITE = "\033[97m"
GRAY = "\033[38;5;245m"
DIM = "\033[2m"


# ============================================================
# Basic helpers
# ============================================================

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except (OSError, UnicodeDecodeError):
        return None


def get_local_version():
    version = read_file(VERSION_FILE)

    if not version:
        return "unknown"

    return version.strip()


def parse_version(version):
    """
    Converts versions such as:
        1.2
        1.21
        2.0.1
        v1.21

    into tuples that can be compared safely.
    """
    if not version:
        return ()

    version = version.strip().lower()

    if version.startswith("v"):
        version = version[1:]

    parts = []

    for part in version.split("."):
        number = ""

        for char in part:
            if char.isdigit():
                number += char
            else:
                break

        if not number:
            parts.append(0)
        else:
            parts.append(int(number))

    while len(parts) < 3:
        parts.append(0)

    return tuple(parts)


def versions_equal(local, remote):
    return parse_version(local) == parse_version(remote)


def version_is_newer(remote, local):
    return parse_version(remote) > parse_version(local)


# ============================================================
# GitHub updater
# ============================================================

def get_remote_version():
    """
    Gets the current version directly from:

    GitHub API
    /repos/walizka/cloudfetch/contents/version?ref=main

    GitHub returns the file contents as base64.
    """

    request = urllib.request.Request(
        GITHUB_API,
        headers={
            "User-Agent": "cloudfetch-updater",
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        encoded_content = data.get("content")

        if not encoded_content:
            raise RuntimeError("GitHub API returned no version content.")

        content = encoded_content.replace("\n", "")

        remote_version = base64.b64decode(content).decode(
            "utf-8"
        ).strip()

        if not remote_version:
            raise RuntimeError("Remote version is empty.")

        return remote_version

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code}."
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to GitHub: {error.reason}"
        ) from error

    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Invalid response from GitHub: {error}"
        ) from error


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "cloudfetch-updater",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()

    with open(destination, "wb") as file:
        file.write(data)


def run_updater():
    print()
    print(f"{CYAN}{BOLD}cloudfetch updater{RESET}")
    print()

    local_version = get_local_version()

    print(
        f"{GRAY}Current version:{RESET} {WHITE}{local_version}{RESET}"
    )

    print(
        f"{GRAY}Checking for updates...{RESET}"
    )

    try:
        remote_version = get_remote_version()
    except RuntimeError as error:
        print()
        print(
            f"{PURPLE}Update check failed:{RESET} {error}"
        )
        return 1

    print(
        f"{GRAY}Latest version:{RESET} {WHITE}{remote_version}{RESET}"
    )
    print()

    if versions_equal(local_version, remote_version):
        print(
            f"{CYAN}cloudfetch is already up to date.{RESET}"
        )
        return 0

    if not version_is_newer(remote_version, local_version):
        print(
            f"{GRAY}Local version is newer than the remote version.{RESET}"
        )
        print(
            f"{GRAY}No update needed.{RESET}"
        )
        return 0

    print(
        f"{CYAN}Update available.{RESET}"
    )

    print(
        f"{GRAY}{local_version} → {remote_version}{RESET}"
    )
    print()

    installer_url = (
        f"{REPO}/releases/download/"
        f"{remote_version}/install.sh"
    )

    installer_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix="cloudfetch-installer-",
            suffix=".sh",
            delete=False,
        ) as temporary_file:
            installer_path = temporary_file.name

        print(
            f"{GRAY}Downloading installer "
            f"from Release {remote_version}...{RESET}"
        )

        download_file(
            installer_url,
            installer_path,
        )

        os.chmod(
            installer_path,
            0o700,
        )

        print(
            f"{CYAN}Installer downloaded.{RESET}"
        )

        print(
            f"{GRAY}Running installer in update mode...{RESET}"
        )
        print()

        # IMPORTANT:
        # The release installer supports:
        #
        #   bash install.sh
        #
        # for a normal installation and:
        #
        #   bash install.sh --upd
        #
        # for updating an existing cloudfetch installation.
        result = subprocess.run(
            [
                "bash",
                installer_path,
                "--upd",
            ],
            check=False,
        )

        if result.returncode != 0:
            print()
            print(
                f"{PURPLE}Update failed "
                f"with exit code {result.returncode}.{RESET}"
            )

            return result.returncode

        print()

        print(
            f"{CYAN}cloudfetch updated successfully "
            f"to {remote_version}.{RESET}"
        )

        return 0

    except urllib.error.HTTPError as error:
        print()
        print(
            f"{PURPLE}Update failed: HTTP "
            f"{error.code}{RESET}"
        )

        return 1

    except urllib.error.URLError as error:
        print()
        print(
            f"{PURPLE}Update failed: "
            f"{error.reason}{RESET}"
        )

        return 1

    except OSError as error:
        print()
        print(
            f"{PURPLE}Update failed: {error}{RESET}"
        )

        return 1

    finally:
        if installer_path:
            try:
                os.remove(installer_path)
            except OSError:
                pass


def show_version():
    print(
        f"cloudfetch version {get_local_version()}"
    )


# ============================================================
# System information
# ============================================================

def get_distro():
    content = read_file(
        "/etc/genix/configuration.toml"
    )

    if content:
        for line in content.splitlines():
            line = line.strip()

            if line.startswith("pretty_name") and "=" in line:
                return (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                )

    content = read_file("/etc/os-release")

    if content:
        for line in content.splitlines():
            if line.startswith("PRETTY_NAME="):
                return (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                )

            if line.startswith("NAME="):
                return (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                )

    return None


def get_kernel():
    return platform.release()


def get_cpu():
    content = read_file("/proc/cpuinfo")

    if content:
        for line in content.splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()

    return platform.processor() or None


def get_udev_properties(sys_path):
    try:
        result = subprocess.run(
            [
                "udevadm",
                "info",
                "--query=property",
                "--path=" + sys_path,
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )

        if result.returncode != 0:
            return {}

        properties = {}

        for line in result.stdout.splitlines():
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            properties[key] = value

        return properties

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return {}


def get_gpu():
    drm_path = "/sys/class/drm"
    gpus = []

    try:
        entries = sorted(os.listdir(drm_path))
    except OSError:
        return None

    for entry in entries:
        if not entry.startswith("card"):
            continue

        if "-" in entry:
            continue

        card_path = os.path.join(
            drm_path,
            entry,
        )

        device_path = os.path.join(
            card_path,
            "device",
        )

        if not os.path.isdir(device_path):
            continue

        vendor = read_file(
            os.path.join(
                device_path,
                "vendor",
            )
        )

        device = read_file(
            os.path.join(
                device_path,
                "device",
            )
        )

        if not vendor or not device:
            continue

        uevent = read_file(
            os.path.join(
                device_path,
                "uevent",
            )
        )

        uevent_data = {}

        if uevent:
            for line in uevent.splitlines():
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                uevent_data[key] = value

        udev = get_udev_properties(
            f"/class/drm/{entry}/device"
        )

        name = (
            udev.get("ID_MODEL_FROM_DATABASE")
            or udev.get("ID_MODEL")
            or udev.get("ID_NAME_FROM_DATABASE")
            or udev.get("ID_NAME")
            or uevent_data.get("DRIVER")
        )

        if name:
            name = name.replace("_", " ")
            name = name.strip()

        vendor_name = {
            "0x1002": "AMD",
            "0x8086": "Intel",
            "0x10de": "NVIDIA",
            "0x102b": "Matrox",
            "0x1013": "Cirrus Logic",
            "0x1a03": "ASPEED",
            "0x5143": "Qualcomm",
            "0x13b5": "ARM",
        }.get(vendor.lower())

        generic_names = (
            "amdgpu",
            "i915",
            "xe",
            "nouveau",
            "nvidia",
            "nvidia_drm",
            "radeon",
            "virtio_gpu",
            "vmwgfx",
        )

        if (
            name
            and name.lower() not in generic_names
        ):
            if (
                vendor_name
                and not name.lower().startswith(
                    vendor_name.lower()
                )
            ):
                name = f"{vendor_name} {name}"

            gpus.append(name)
            continue

        if vendor_name:
            gpus.append(
                f"{vendor_name} GPU "
                f"(PCI {device.lower()})"
            )
        else:
            gpus.append(
                f"PCI GPU "
                f"{vendor.lower()}:{device.lower()}"
            )

    if not gpus:
        return None

    unique = []

    for gpu in gpus:
        if gpu not in unique:
            unique.append(gpu)

    return " / ".join(unique)


def get_local_ip():
    sock = None

    try:
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )

        sock.settimeout(1)

        sock.connect(
            ("1.1.1.1", 80)
        )

        return sock.getsockname()[0]

    except OSError:
        return None

    finally:
        if sock:
            sock.close()


def get_ram():
    content = read_file(
        "/proc/meminfo"
    )

    if not content:
        return None

    memory = {}

    for line in content.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1,
        )

        try:
            memory[key] = int(
                value.strip().split()[0]
            )
        except (
            ValueError,
            IndexError,
        ):
            continue

    total = memory.get("MemTotal")
    available = memory.get("MemAvailable")

    if total is None or available is None:
        return None

    used = total - available

    used_gib = used / 1024 / 1024
    total_gib = total / 1024 / 1024

    return (
        f"{used_gib:.1f} GiB / "
        f"{total_gib:.1f} GiB"
    )


def get_shell():
    shell = os.environ.get("SHELL")

    if shell:
        return os.path.basename(shell)

    return None


# ============================================================
# Window manager detection
# ============================================================

KNOWN_WMS = {
    "dwm": "dwm",
    "vxwm": "vxwm",
    "cloudwm": "cloudwm",

    "hyprland": "Hyprland",
    "sway": "Sway",
    "i3": "i3",
    "i3-gaps": "i3-gaps",
    "bspwm": "bspwm",
    "awesome": "Awesome",
    "openbox": "Openbox",
    "xfwm4": "Xfwm4",
    "kwin": "KWin",
    "kwin_x11": "KWin",
    "kwin_wayland": "KWin",
    "mutter": "Mutter",
    "marco": "Marco",
    "metacity": "Metacity",
    "icewm": "IceWM",
    "fluxbox": "Fluxbox",
    "jwm": "JWM",
    "herbstluftwm": "herbstluftwm",
    "spectrwm": "spectrwm",
    "qtile": "Qtile",
    "leftwm": "LeftWM",
    "river": "River",
    "wayfire": "Wayfire",
    "labwc": "LabWC",
    "niri": "Niri",
    "cage": "Cage",
    "dwl": "dwl",
    "xmonad": "XMonad",
    "ratpoison": "Ratpoison",
    "wmii": "wmii",
    "pekwm": "PekWM",
    "notion": "Notion",
    "stumpwm": "StumpWM",
    "wmaker": "Window Maker",
    "enlightenment": "Enlightenment",
}


def is_cloudwm_running():
    return os.path.exists(
        "/tmp/cloudwm.sock"
    )


def get_wm():
    # cloudwm has its own control socket.
    # Check it first so it is detected even when
    # desktop environment variables are empty.
    if is_cloudwm_running():
        return "cloudwm"

    for variable in (
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_DESKTOP",
        "DESKTOP_SESSION",
    ):
        value = os.environ.get(variable)

        if not value:
            continue

        value = value.strip()

        for wm in KNOWN_WMS:
            if value.lower() == wm.lower():
                return KNOWN_WMS[wm]

    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue

            comm = read_file(
                f"/proc/{pid}/comm"
            )

            if not comm:
                continue

            process_name = comm.strip().lower()

            if process_name in KNOWN_WMS:
                return KNOWN_WMS[
                    process_name
                ]

    except OSError:
        pass

    return None


# ============================================================
# Output
# ============================================================

def shorten(text, length=31):
    if len(text) <= length:
        return text

    return text[:length - 1] + "…"


def print_logo():
    logo = [
        "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⠼⠟⠛⠛⠣⠤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
        "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⢠⡿⠋⠃⠀⠀⠀⠀⠀⠀⠘⠟⢄⡀⠀⠀⠀⠀⠀⠀",
        "⠀⠀⠀⠀⠀⠀⠀⠀⢀⡼⡟⣯⡿⠛⠛⠿⠕⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠺⣃⠀⠀⠀⠀⠀⠀",
        "⠀⠀⠀⠀⣀⠰⠟⠛⠻⠿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡿⠶⠶⢆⣀⠀⠀⠀",
        "⠀⠀⣠⡾⠉⠀⠀⠀⠀⠀⠑⠃⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠈⠀⠀⠀⠈⢻⡷⣀⠀",
        "⠀⢀⣼⠇⡁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⠳⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⡆",
        "⠀⢸⡇⠀⠈⢀⠀⠀⠀⠀⠀⠀⠀⡆⢀⠀⠀⠀⠀⠀⠜⠀⠀⠀⠀⠀⠀⠀⠴⡀⠀⠀⠰⠀⢸⡇",
        "⠀⠀⢱⣆⠀⠈⠓⠒⠒⠚⢅⣶⡊⠀⠈⠸⡉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⠆⠈⠀⠀⠀⣾⠁",
        "⠀⠀⠀⠛⢗⣐⣠⣤⣐⾾⣿⣿⣿⣷⣀⡄⢀⡠⢡⣶⣶⣶⡀⠀⠀⠀⠀⠀⡰⢧⣀⣼⣶⣾⠟⠀⠀",
        "⠀⠀⠀⠀⠀⠀⠀⠀⠉⢿⡼⠿⢿⣿⡿⠋⠉⠉⠉⠸⣿⠯⣿⣶⣶⣶⣿⡿⠏⠉⠉⠁⠀⠀⠀⠀",
        "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠋⠉⠀⠀⠀⠀⠀⠀⠀⠋⠻⠿⠿⠏⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    ]

    for index, line in enumerate(logo):
        if index < 4:
            print(
                f"{CYAN}{line}{RESET}"
            )
        elif index < 8:
            print(
                f"{BLUE}{line}{RESET}"
            )
        else:
            print(
                f"{PURPLE}{line}{RESET}"
            )


def print_system_info():
    information = [
        ("os", get_distro()),
        ("kernel", get_kernel()),
        ("cpu", get_cpu()),
        ("gpu", get_gpu()),
        ("local-ip", get_local_ip()),
        ("ram", get_ram()),
        ("sh", get_shell()),
        ("wm", get_wm()),
    ]

    information = [
        (name, value)
        for name, value in information
        if value
    ]

    print()
    print_logo()
    print()

    print(
        f" {GRAY}╭────────────────────────────────────────╮{RESET}"
    )

    print(
        f" {GRAY}│{RESET} "
        f"{CYAN}{BOLD}cloudfetch{RESET}"
        f"{GRAY} │{RESET}"
    )

    print(
        f" {GRAY}├────────────────────────────────────────┤{RESET}"
    )

    for label, value in information:
        value = shorten(
            str(value)
        )

        print(
            f" {GRAY}│{RESET} "
            f"{PURPLE}{label:<8}{RESET}"
            f"{WHITE}{value:<31}{RESET}"
            f"{GRAY}│{RESET}"
        )

    print(
        f" {GRAY}╰────────────────────────────────────────╯{RESET}"
    )

    print()


# ============================================================
# CLI
# ============================================================

def print_help():
    print(
        f"""
{CYAN}{BOLD}cloudfetch{RESET}

Usage:
  cf
  cf -v
  cf --version
  cf version

  cf -upd
  cf --update
  cf update

Options:
  -v, --version     Show installed cloudfetch version
  -upd, --update    Check GitHub for updates
  update            Check GitHub for updates
  help              Show this help
"""
    )


def main():
    args = sys.argv[1:]

    if not args:
        print_system_info()
        return 0

    command = args[0].lower()

    if command in (
        "-v",
        "--version",
        "version",
    ):
        show_version()
        return 0

    if command in (
        "-upd",
        "--update",
        "update",
    ):
        return run_updater()

    if command in (
        "-h",
        "--help",
        "help",
    ):
        print_help()
        return 0

    print(
        f"{PURPLE}Unknown command:{RESET} "
        f"{command}"
    )

    print_help()

    return 1


if __name__ == "__main__":
    sys.exit(main())
