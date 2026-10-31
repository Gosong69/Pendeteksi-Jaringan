import platform
import re
import subprocess


def get_ssid():
    """Nama wifi yang sedang dipakai. None kalau kabel LAN atau tidak terbaca."""
    if platform.system() != "Windows":
        return None
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"], text=True, errors="ignore"
        )
    except Exception:
        return None
    for line in out.splitlines():
        baris = line.strip()
        if baris.startswith("SSID") and not baris.startswith("BSSID"):
            return baris.split(":", 1)[1].strip() or None
    return None


def get_gateway():
    """IP router di jaringan yang sedang aktif."""
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["route", "print", "-4", "0.0.0.0"], text=True, errors="ignore"
            )
            for line in out.splitlines():
                p = line.split()
                if len(p) >= 5 and p[0] == "0.0.0.0" and p[1] == "0.0.0.0":
                    return p[2]
        else:
            out = subprocess.check_output(["ip", "route"], text=True)
            m = re.search(r"default via (\S+)", out)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None