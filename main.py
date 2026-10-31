
import subprocess
import platform
from datetime import datetime
from info_network import get_ssid, get_gateway


# ==================================
# HOME NETWORK MONITORING
# ==================================

print("=" * 40)
print("       HOME NETWORK MONITORING")
print("=" * 40)

ssid = get_ssid() or "kabel/LAN"
gateway = get_gateway()

print("Wifi    :", ssid)
print("Gateway :", gateway)

PERANGKAT_RUMAH = [
    {"name": "TOTOLINK N300RT", "ip": "192.168.1.1"},
    {"name": "TP-Link TL-WR820N", "ip": "192.168.1.2"},
]

if ssid == "NAMA_WIFI_RUMAH":
    devices = PERANGKAT_RUMAH
else:
    devices = [{"name": f"Router ({ssid})", "ip": gateway}] if gateway else []

# Menentukan perintah ping berdasarkan OS
if platform.system() == "Windows":
    ping_command = ["ping", "-n", "1", "-w", "2000"]
else:
    ping_command = ["ping", "-c", "1", "-W", "2"]


# Fungsi pemeriksaan perangkat
def check_device(name, ip):

    print(f"\nMemeriksa: {name}")
    print(f"IP Address: {ip}")

    try:
        result = subprocess.run(
            ping_command + [ip],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            status = "ONLINE"
        else:
            status = "OFFLINE"

    except Exception as error:
        status = "ERROR"
        print("Pesan:", error)

    print(f"Status: {status}")

    return status


# Waktu pemeriksaan
print("Waktu:", datetime.now().strftime("%d-%m-%Y %H:%M:%S"))

print("\n--- DEVICE MONITORING ---")

# Memeriksa semua perangkat
for device in devices:

    check_device(
        device["name"],
        device["ip"]
    )

print("\n" + "=" * 40)
print("       MONITORING SELESAI")
print("=" * 40)
