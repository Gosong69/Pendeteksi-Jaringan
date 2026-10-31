from flask import Flask, render_template, jsonify, request
from wifi_scanner import detect_network, scan_network_data, JaringanTidakDiizinkan
from info_network import get_ssid

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan")
def api_scan():
    """Endpoint untuk memindai jaringan dan mengembalikan data perangkat."""
    network = detect_network()
    if not network:
        return jsonify({"error": "Tidak dapat mendeteksi jaringan."}), 500

    try:
        devices = scan_network_data(network)
        ssid = get_ssid() or "kabel/LAN"
        return jsonify({"network": network, "ssid": ssid, "devices": devices})
    except JaringanTidakDiizinkan as e:
        return jsonify({"error": str(e)}), 403
    except PermissionError:
        return jsonify({"error": "Jalankan Flask sebagai Administrator untuk ARP scan."}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices")
def api_devices():
    """Endpoint untuk mengambil riwayat perangkat dari database."""
    from database import get_connection
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT ip_address, mac_address, network, ssid, first_seen, last_seen "
            "FROM network_devices ORDER BY last_seen DESC"
        )
        rows = cursor.fetchall()
        # Konversi datetime ke string agar JSON-serializable
        for row in rows:
            if row.get("first_seen"):
                row["first_seen"] = row["first_seen"].strftime("%d %b %Y, %H:%M")
            if row.get("last_seen"):
                row["last_seen"] = row["last_seen"].strftime("%d %b %Y, %H:%M")
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route("/api/devices/old", methods=["DELETE"])
def delete_old_devices():
    """Hapus perangkat yang last_seen lebih dari 90 hari lalu."""
    from database import get_connection
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM network_devices WHERE last_seen < NOW() - INTERVAL 90 DAY"
        )
        connection.commit()
        deleted = cursor.rowcount
        return jsonify({"message": f"{deleted} perangkat lama berhasil dihapus.", "deleted": deleted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route("/api/devices/<path:mac>", methods=["DELETE"])
def delete_device(mac):
    """Hapus satu perangkat berdasarkan MAC address (+ network & ssid opsional)."""
    from database import get_connection
    network = request.args.get("network", "")
    ssid = request.args.get("ssid", "")
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        if network and ssid:
            cursor.execute(
                "DELETE FROM network_devices WHERE mac_address = %s AND network = %s AND ssid = %s",
                (mac, network, ssid)
            )
        else:
            cursor.execute(
                "DELETE FROM network_devices WHERE mac_address = %s",
                (mac,)
            )
        connection.commit()
        deleted = cursor.rowcount
        return jsonify({"message": f"{deleted} perangkat berhasil dihapus.", "deleted": deleted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    app.run(debug=True)
