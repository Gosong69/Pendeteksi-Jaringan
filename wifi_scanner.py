
import socket
import ipaddress
import psutil
import mysql.connector

from scapy.all import ARP, Ether, srp, conf
from datetime import datetime
from database import get_connection


# ==========================================
# DATABASE HELPER
# ==========================================

def save_to_database(devices):
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO network_devices (ip_address, mac_address, first_seen, last_seen)
        VALUES (%s, %s, %s, %s)
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
        if connection and connection.is_connected():
            cursor.close()
            connection.close()



# ==========================================
# AUTOMATIC NETWORK DETECTION
# ==========================================

def detect_network():

    print("\nMendeteksi jaringan otomatis...")

    # Mendeteksi IP yang digunakan untuk
    # koneksi dengan jaringan luar
    try:
        test_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        test_socket.connect(("8.8.8.8", 80))
        local_ip = test_socket.getsockname()[0]
        test_socket.close()

    except OSError:
        print("Tidak dapat mendeteksi jaringan.")
        return None

    # Mencari subnet mask interface tersebut
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
# WIFI NETWORK SCANNER
# ==========================================

def scan_network(network):

    print("\n" + "=" * 55)
    print("             WIFI NETWORK SCANNER")
    print("=" * 55)

    print("Waktu scan:", datetime.now())
    print("Jaringan  :", network)

    print("\nSedang memindai perangkat...\n")

    # Membuat ARP request
    arp = ARP(pdst=network)

    # Broadcast Ethernet
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")

    packet = ether / arp

    # Mengirim paket ARP
    answered, unanswered = srp(
        packet,
        timeout=3,
        verbose=False
    )

    print("-" * 65)
    print(f"{'IP ADDRESS':<22}{'MAC ADDRESS':<25}")
    print("-" * 65)

   
    devices_to_save = []

    for sent, received in answered:

        ip = received.psrc
        mac = received.hwsrc

        print(f"{ip:<22}{mac:<25}")

        devices_to_save.append((
            ip,
            mac,
            datetime.now(),
            datetime.now()
        ))

    print("-" * 65)

    print("Total perangkat:", len(answered))

    # Simpan hasil ke database
    if devices_to_save:
        save_to_database(devices_to_save)
    else:
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

        except PermissionError:
            print("\nJalankan program sebagai Administrator.")

        except Exception as error:
            print("\nTerjadi kesalahan:", error)

    print("\nMonitoring selesai.")
