
import socket
import ipaddress
import psutil


from scapy.all import ARP, Ether, srp
from datetime import datetime
from database import get_connection
from info_network import get_ssid

# ==========================================
# JARINGAN YANG DIIZINKAN
# ==========================================

# Jaringan yang boleh dipindai: (network, ssid)
JARINGAN_DIIZINKAN = [
    ("192.168.1.0/24", "NAMA_WIFI_RUMAH"),
    ("192.168.210.0/24", "kabel/LAN"),
    # Tambahkan jaringan lain HANYA jika kamu punya izin memindainya, contoh:
    # ("192.168.43.0/24", "NAMA_HOTSPOT_HP"),
    # Untuk kabel LAN, ssid-nya ditulis "kabel/LAN"
]

MAKS_ALAMAT = 1024  # subnet lebih besar dari ini tidak dipindai


class JaringanTidakDiizinkan(Exception):
    pass


def cek_jaringan(network, ssid):
    if (network, ssid) not in JARINGAN_DIIZINKAN:
        raise JaringanTidakDiizinkan(
            f"Jaringan '{ssid}' ({network}) belum ada di JARINGAN_DIIZINKAN."
        )
    if ipaddress.ip_network(network).num_addresses > MAKS_ALAMAT:
        raise JaringanTidakDiizinkan(
            f"Jaringan {network} terlalu besar untuk ARP scan."
        )


# ==========================================
# DATABASE HELPER
# ==========================================


def save_to_database(devices):
    """Simpan daftar perangkat ke database MySQL."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO network_devices
            (ip_address, mac_address, first_seen, last_seen, network, ssid)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            ip_address = VALUES(ip_address),
            last_seen = VALUES(last_seen)
        """

        cursor.executemany(query, devices)
        connection.commit()
        print(f"Berhasil menyimpan {len(devices)} perangkat ke database.")

    except Exception as error:
        print("Gagal menyimpan ke database:", error)

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# ==========================================
# AUTOMATIC NETWORK DETECTION
# ==========================================

def detect_network():
    """Deteksi jaringan lokal secara otomatis. Mengembalikan string CIDR atau None."""

    print("\nMendeteksi jaringan otomatis...")

    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.connect(("8.8.8.8", 80))
        local_ip = test_socket.getsockname()[0]
        test_socket.close()
    except OSError:
        print("Tidak dapat mendeteksi jaringan.")
        return None

    for interface, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            if (
                address.family == socket.AF_INET
                and address.address == local_ip
                and address.netmask
            ):
                network = ipaddress.ip_interface(
                    f"{local_ip}/{address.netmask}"
                ).network

                print("Interface :", interface)
                print("IP Address:", local_ip)
                print("Subnet    :", address.netmask)
                print("Network   :", network)

                return str(network)

    print("Interface jaringan tidak ditemukan.")
    return None


# ==========================================
# WIFI NETWORK SCANNER (mengembalikan data)
# ==========================================

def scan_network_data(network):
    """
    Pindai jaringan menggunakan ARP dan kembalikan list dict perangkat.
    Juga menyimpan hasilnya ke database.
    Membutuhkan hak Administrator.
    """
    now = datetime.now()

    ssid = get_ssid() or "kabel/LAN"
    cek_jaringan(network, ssid)

    arp    = ARP(pdst=network)
    ether  = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp

    answered, _ = srp(packet, timeout=3, verbose=False)

    devices      = []
    devices_to_save = []

    for sent, received in answered:
        ip  = received.psrc
        mac = received.hwsrc

        devices.append({
            "ip":        ip,
            "mac":       mac,
            "last_seen": now.strftime("%d-%m-%Y %H:%M:%S"),
            "network":   network,
            "ssid":      ssid,
        })

        devices_to_save.append((ip, mac, now, now, network, ssid))

    if devices_to_save:
        save_to_database(devices_to_save)

    return devices


def scan_network(network):
    """Pindai jaringan dan cetak hasilnya ke konsol (mode CLI)."""

    print("\n" + "=" * 55)
    print("             WIFI NETWORK SCANNER")
    print("=" * 55)
    print("Waktu scan:", datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
    print("Jaringan  :", network)
    print("\nSedang memindai perangkat...\n")

    devices = scan_network_data(network)

    print("-" * 65)
    print(f"{'IP ADDRESS':<22}{'MAC ADDRESS':<25}{'WAKTU':<20}")
    print("-" * 65)

    for d in devices:
        print(f"{d['ip']:<22}{d['mac']:<25}{d['last_seen']:<20}")

    print("-" * 65)
    print("Total perangkat:", len(devices))

    if not devices:
        print("Tidak ada perangkat yang ditemukan.")


# ==========================================
# MAIN PROGRAM
# ==========================================

if __name__ == "__main__":

    print("HOME NETWORK MONITORING SYSTEM")

    detected_network = detect_network()

    if detected_network:
        try:
            scan_network(detected_network)
        except JaringanTidakDiizinkan as error:
            print("\n", error)
        except PermissionError:
            print("\nJalankan program sebagai Administrator.")
        except Exception as error:
            print("\nTerjadi kesalahan:", error)

    print("\nMonitoring selesai.")
