#!/usr/bin/env python3

import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[38;5;117m"
BLUE = "\033[38;5;111m"
PURPLE = "\033[38;5;183m"
WHITE = "\033[97m"
GRAY = "\033[38;5;245m"


REPO = "https://github.com/walizka/cloudfetch"
RAW_REPO = "https://raw.githubusercontent.com/walizka/cloudfetch/main"
VERSION_URL = f"{RAW_REPO}/version"


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except (OSError, UnicodeDecodeError):
        return None


def get_distro():
    content = read_file("/etc/genix/configuration.toml")

    if content:
        for line in content.splitlines():
            line = line.strip()

            if line.startswith("pretty_name") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"')

    content = read_file("/etc/os-release")

    if content:
        for line in content.splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')

            if line.startswith("NAME="):
                return line.split("=", 1)[1].strip().strip('"')

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

    except (OSError, subprocess.SubprocessError):
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

        card_path = os.path.join(drm_path, entry)
        device_path = os.path.join(card_path, "device")

        if not os.path.isdir(device_path):
            continue

        vendor = read_file(
            os.path.join(device_path, "vendor")
        )

        device = read_file(
            os.path.join(device_path, "device")
        )

        if not vendor or not device:
            continue

        uevent = read_file(
            os.path.join(device_path, "uevent")
        )

        uevent_data = {}

        if uevent:
            for line in uevent.splitlines():
                if "=" in line:
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
            name = name.replace("_", " ").strip()

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

        if name and name.lower() not in (
            "amdgpu",
            "i915",
            "xe",
            "nouveau",
            "nvidia",
            "nvidia_drm",
            "radeon",
            "virtio_gpu",
            "vmwgfx",
        ):
            if vendor_name and not name.lower().startswith(
                vendor_name.lower()
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
        sock.connect(("1.1.1.1", 80))

        return sock.getsockname()[0]

    except OSError:
        return None

    finally:
        if sock:
            sock.close()


def get_ram():
    content = read_file("/proc/meminfo")

    if not content:
        return None

    memory = {}

    for line in content.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        try:
            memory[key] = int(
                value.strip().split()[0]
            )
        except (ValueError, IndexError):
            continue

    total = memory.get("MemTotal")
    available = memory.get("MemAvailable")

    if total is None or available is None:
        return None

    used = total - available

    used_gib = used / 1024 / 1024
    total_gib = total / 1024 / 1024

    return f"{used_gib:.1f} GiB / {total_gib:.1f} GiB"


def get_shell():
    shell = os.environ.get("SHELL")

    if shell:
        return os.path.basename(shell)

    return None


KNOWN_WMS = {
    "cloudwm": "CloudWM",
    "dwm": "dwm",
    "vxwm": "vxwm",
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
    socket_path = "/tmp/cloudwm.sock"

    if not os.path.exists(socket_path):
        return False

    sock = None

    try:
        sock = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        )

        sock.settimeout(0.2)
        sock.connect(socket_path)
        sock.sendall(b"help\n")

        try:
            sock.recv(128)
        except socket.timeout:
            pass

        return True

    except OSError:
        return False

    finally:
        if sock:
            sock.close()


def get_wm():
    for variable in (
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_DESKTOP",
        "DESKTOP_SESSION",
    ):
        value = os.environ.get(variable)

        if value:
            value = value.strip().lower()

            if value in KNOWN_WMS:
                return KNOWN_WMS[value]

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
                return KNOWN_WMS[process_name]

    except OSError:
        pass

    if is_cloudwm_running():
        return "CloudWM"

    return None


def parse_version(version):
    if not version:
        return None

    version = version.strip()

    if version.startswith("v"):
        version = version[1:]

    parts = version.split(".")

    result = []

    for part in parts:
        if not part.isdigit():
            return None

        result.append(int(part))

    return tuple(result)


def get_local_version():
    version_file = os.path.expanduser(
        "~/.cloudfetch/version"
    )

    return read_file(version_file)


def get_remote_version():
    try:
        request = urllib.request.Request(
            VERSION_URL,
            headers={
                "User-Agent": "cloudfetch-updater",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=10,
        ) as response:
            version = response.read().decode(
                "utf-8"
            ).strip()

        return version or None

    except (
        OSError,
        urllib.error.URLError,
        UnicodeDecodeError,
    ):
        return None


def version_is_newer(local, remote):
    local_version = parse_version(local)
    remote_version = parse_version(remote)

    if remote_version is None:
        return False

    if local_version is None:
        return True

    length = max(
        len(local_version),
        len(remote_version),
    )

    local_version = local_version + (
        0,
    ) * (length - len(local_version))

    remote_version = remote_version + (
        0,
    ) * (length - len(remote_version))

    return remote_version > local_version


def save_local_version(version):
    directory = os.path.expanduser(
        "~/.cloudfetch"
    )

    os.makedirs(
        directory,
        exist_ok=True,
    )

    version_file = os.path.join(
        directory,
        "version",
    )

    with open(
        version_file,
        "w",
        encoding="utf-8",
    ) as file:
        file.write(
            version.strip() + "\n"
        )


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "cloudfetch-updater",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        data = response.read()

    with open(
        destination,
        "wb",
    ) as file:
        file.write(data)


def update_cloudfetch():
    print()
    print(
        f"{CYAN}{BOLD}cloudfetch updater{RESET}"
    )
    print()

    local_version = get_local_version()

    if local_version:
        print(
            f"{GRAY}Current version:{RESET} "
            f"{WHITE}{local_version}{RESET}"
        )
    else:
        print(
            f"{GRAY}Current version:{RESET} "
            f"{WHITE}unknown{RESET}"
        )

    print(
        f"{GRAY}Checking for updates...{RESET}"
    )

    remote_version = get_remote_version()

    if remote_version is None:
        print()
        print(
            f"{PURPLE}"
            f"Could not retrieve the latest "
            f"version."
            f"{RESET}"
        )
        print()

        return 1

    print(
        f"{GRAY}Latest version:{RESET} "
        f"{WHITE}{remote_version}{RESET}"
    )

    if not version_is_newer(
        local_version,
        remote_version,
    ):
        print()
        print(
            f"{CYAN}"
            f"cloudfetch is already up to date."
            f"{RESET}"
        )
        print()

        return 0

    print()
    print(
        f"{CYAN}Update available.{RESET}"
    )

    print(
        f"{GRAY}"
        f"{local_version or 'unknown'}"
        f" → "
        f"{remote_version}"
        f"{RESET}"
    )

    installer_url = (
        f"{REPO}/releases/download/"
        f"{remote_version}/install.sh"
    )

    print()
    print(
        f"{GRAY}Downloading installer from "
        f"Release {remote_version}...{RESET}"
    )

    installer_path = None

    try:
        file_descriptor, installer_path = (
            tempfile.mkstemp(
                prefix="cloudfetch-",
                suffix="-install.sh",
            )
        )

        os.close(file_descriptor)

        download_file(
            installer_url,
            installer_path,
        )

        os.chmod(
            installer_path,
            0o700,
        )

        print(
            f"{GRAY}Installer downloaded.{RESET}"
        )

        print(
            f"{GRAY}Running installer...{RESET}"
        )

        print()

        result = subprocess.run(
            [
                "bash",
                installer_path,
            ],
            check=False,
        )

        if result.returncode != 0:
            print()
            print(
                f"{PURPLE}"
                f"Installer failed with exit code "
                f"{result.returncode}."
                f"{RESET}"
            )

            return result.returncode

        save_local_version(
            remote_version
        )

        print()
        print(
            f"{CYAN}{BOLD}"
            f"cloudfetch updated successfully!"
            f"{RESET}"
        )

        print(
            f"{GRAY}Version:{RESET} "
            f"{WHITE}{remote_version}{RESET}"
        )

        return 0

    except urllib.error.HTTPError as error:
        print()
        print(
            f"{PURPLE}"
            f"Failed to download installer:"
            f"{RESET}"
        )

        print(
            f"{GRAY}"
            f"HTTP {error.code}: {error.reason}"
            f"{RESET}"
        )

        print(
            f"{GRAY}"
            f"URL: {installer_url}"
            f"{RESET}"
        )

        return 1

    except (
        urllib.error.URLError,
        OSError,
    ) as error:
        print()
        print(
            f"{PURPLE}"
            f"Failed to update cloudfetch:"
            f"{RESET}"
        )

        print(
            f"{GRAY}{error}{RESET}"
        )

        return 1

    finally:
        if installer_path:
            try:
                os.remove(installer_path)
            except OSError:
                pass


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
        "⠀⠀⠀⠛⢗⣐⣠⣤⣐⣾⣿⣿⣷⣀⡄⢀⡠⢡⣶⣶⣶⡀⠀⠀⠀⠀⠀⡰⢧⣀⣼⣶⣾⠟⠀⠀",
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


def print_help():
    print()
    print(
        f"{CYAN}{BOLD}cloudfetch{RESET}"
    )
    print()

    print(
        f"  {WHITE}cf{RESET}"
        f"              Show system information"
    )

    print(
        f"  {WHITE}cf -upd{RESET}"
        f"           Check for updates"
    )

    print(
        f"  {WHITE}cf --update{RESET}"
        f"       Check for updates"
    )

    print(
        f"  {WHITE}cf update{RESET}"
        f"           Check for updates"
    )

    print(
        f"  {WHITE}cf -h{RESET}"
        f"              Show help"
    )

    print(
        f"  {WHITE}cf --help{RESET}"
        f"          Show help"
    )

    print()


def print_fetch():
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
        f"    {GRAY}"
        f"╭────────────────────────────────────────╮"
        f"{RESET}"
    )

    print(
        f"    {GRAY}│{RESET} "
        f"{CYAN}{BOLD}cloudfetch{RESET}"
        f"{GRAY}"
        f"                              │"
        f"{RESET}"
    )

    print(
        f"    {GRAY}"
        f"├────────────────────────────────────────┤"
        f"{RESET}"
    )

    for label, value in information:
        value = shorten(str(value))

        print(
            f"    {GRAY}│{RESET} "
            f"{PURPLE}{label:<8}{RESET}"
            f"{WHITE}{value:<31}{RESET}"
            f"{GRAY}│{RESET}"
        )

    print(
        f"    {GRAY}"
        f"╰────────────────────────────────────────╯"
        f"{RESET}"
    )

    print()


def main():
    args = sys.argv[1:]

    if not args:
        print_fetch()
        return 0

    if args[0] in (
        "-upd",
        "--update",
        "update",
    ):
        return update_cloudfetch()

    if args[0] in (
        "-h",
        "--help",
        "help",
    ):
        print_help()
        return 0

    print(
        f"{PURPLE}"
        f"Unknown argument: {args[0]}"
        f"{RESET}"
    )

    print_help()

    return 1


if __name__ == "__main__":
    sys.exit(main())
