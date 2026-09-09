#!/usr/bin/env python3

import os
import platform
import socket
import subprocess

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[38;5;117m"
BLUE = "\033[38;5;111m"
PURPLE = "\033[38;5;183m"
WHITE = "\033[97m"
GRAY = "\033[38;5;245m"
DIM = "\033[2m"


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
            socket.SOCK_DGRAM
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


def get_wm():
    for variable in (
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_DESKTOP",
        "DESKTOP_SESSION",
    ):
        value = os.environ.get(variable)

        if value:
            value = value.strip()

            for wm in KNOWN_WMS:
                if value.lower() == wm.lower():
                    return KNOWN_WMS[wm]

    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue

            comm = read_file(f"/proc/{pid}/comm")

            if not comm:
                continue

            process_name = comm.strip().lower()

            if process_name in KNOWN_WMS:
                return KNOWN_WMS[process_name]

    except OSError:
        pass

    return None


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
            print(f"{CYAN}{line}{RESET}")
        elif index < 8:
            print(f"{BLUE}{line}{RESET}")
        else:
            print(f"{PURPLE}{line}{RESET}")


def main():
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
        f"    {GRAY}╭────────────────────────────────────────╮{RESET}"
    )

    print(
        f"    {GRAY}│{RESET} "
        f"{CYAN}{BOLD}cloudfetch{RESET}"
        f"{GRAY}                              │{RESET}"
    )

    print(
        f"    {GRAY}├────────────────────────────────────────┤{RESET}"
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
        f"    {GRAY}╰────────────────────────────────────────╯{RESET}"
    )

    print()


if __name__ == "__main__":
    main()
