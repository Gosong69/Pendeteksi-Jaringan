
import mysql.connector


def get_connection():

    connection = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="landsturm",
        database="network"
    )

    return connection


def init_db():
    """Buat tabel network_devices jika belum ada."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_devices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ip_address VARCHAR(20) NOT NULL,
                mac_address VARCHAR(20) NOT NULL,
                network VARCHAR(50) NOT NULL DEFAULT '192.168.1.0/24',
                ssid VARCHAR(100) NOT NULL DEFAULT 'kabel/LAN',
                first_seen DATETIME NOT NULL,
                last_seen DATETIME NOT NULL,
                UNIQUE KEY uniq_perangkat (mac_address, network, ssid)
            )
        """)
        connection.commit()
        print("Database siap (tabel network_devices sudah ada atau baru dibuat).")
    except Exception as error:
        print("Gagal inisialisasi database:", error)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# Inisialisasi database saat module diimport
init_db()
