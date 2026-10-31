# Panduan: Pendeteksi Jaringan di Wifi Lain (Multi-Jaringan)

Panduan ini menyesuaikan proyek **Pendeteksi-Jaringan** agar tetap berfungsi dan rapi saat dipakai di luar rumah atau di wifi yang berbeda.

> **Peringatan:** Pindai hanya jaringan milikmu atau jaringan yang kamu punya izin untuk memindainya. Wifi kampus, kafe, atau kantor sering melarang scanning. Kode di bawah memakai daftar jaringan yang diizinkan untuk mencegah scan tidak sengaja.

## Ringkasan perubahan

| File | Perubahan |
|---|---|
| `network_info.py` | **File baru**: pembaca SSID dan gateway |
| MySQL | Tambah kolom `network` dan `ssid` pada tabel `network_devices` |
| `wifi_scanner.py` | Simpan network/ssid, tambah daftar jaringan yang diizinkan |
| `app.py` | Tangani error "jaringan tidak diizinkan", tambah kolom di `/api/devices` |
| `main.py` | Ganti IP router manual dengan gateway otomatis |

Catatan: `detect_network()` di `wifi_scanner.py` sudah mengembalikan `str(network)`, jadi tidak perlu diubah.

---

## 1. Buat file baru `network_info.py`

Letakkan di folder yang sama dengan `main.py`.

```python
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
```

Dipisah ke file sendiri supaya `main.py` bisa memakainya tanpa ikut memuat scapy.

---

## 2. Database (MySQL)

Lihat dulu kunci unik tabel:

```sql
SHOW CREATE TABLE network_devices;
```

Tambahkan kolom. Ganti `NAMA_WIFI_RUMAH` dengan nama wifi rumahmu, dan `192.168.1.0/24` bila jaringan rumahmu berbeda:

```sql
ALTER TABLE network_devices ADD COLUMN network VARCHAR(50), ADD COLUMN ssid VARCHAR(100);
UPDATE network_devices SET network = '192.168.1.0/24', ssid = 'NAMA_WIFI_RUMAH';
ALTER TABLE network_devices
  MODIFY network VARCHAR(50) NOT NULL,
  MODIFY ssid VARCHAR(100) NOT NULL;
```

Ubah kunci unik agar per jaringan. Nama index lihat dari hasil `SHOW CREATE TABLE` (misalnya `mac_address`):

```sql
ALTER TABLE network_devices DROP INDEX mac_address;
ALTER TABLE network_devices ADD UNIQUE KEY uniq_perangkat (mac_address, network, ssid);
```

Kalau `mac_address` ternyata `PRIMARY KEY`, perintahnya perlu disesuaikan dulu.

---

## 3. `wifi_scanner.py`

### a. Impor
Tambahkan di bagian atas:

```python
from network_info import get_ssid
```

### b. Blok jaringan yang diizinkan
Tempel di antara impor dan `# DATABASE HELPER`:

```python
# Jaringan yang boleh dipindai: (network, ssid)
JARINGAN_DIIZINKAN = [
    ("192.168.1.0/24", "NAMA_WIFI_RUMAH"),
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
```

Pembatas ukuran penting di luar rumah: wifi kampus atau kantor sering memakai subnet besar (misalnya `/16`, 65 ribu alamat). ARP scan di sana lambat dan mudah dianggap serangan.

### c. Ganti query di `save_to_database()`

```python
        query = """
        INSERT INTO network_devices
            (ip_address, mac_address, first_seen, last_seen, network, ssid)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            ip_address = VALUES(ip_address),
            last_seen = VALUES(last_seen)
        """
```

### d. Di `scan_network_data()`
Setelah baris `now = datetime.now()` tambahkan:

```python
    ssid = get_ssid() or "kabel/LAN"
    cek_jaringan(network, ssid)
```

Lalu ubah baris `devices_to_save.append(...)` menjadi:

```python
        devices_to_save.append((ip, mac, now, now, network, ssid))
```

### e. Di bagian `__main__`
Tambahkan satu `except` di antara `try` dan `except` yang lain:

```python
        except JaringanTidakDiizinkan as error:
            print("\n", error)
```

---

## 4. `app.py`

Ubah impor di baris 2:

```python
from wifi_scanner import detect_network, scan_network_data, get_ssid, JaringanTidakDiizinkan
```

Di `api_scan()`, ubah bagian `try`:

```python
    try:
        devices = scan_network_data(network)
        return jsonify({"network": network, "ssid": get_ssid(), "devices": devices})
    except JaringanTidakDiizinkan as e:
        return jsonify({"error": str(e)}), 403
    except PermissionError:
        return jsonify({"error": "Jalankan Flask sebagai Administrator untuk ARP scan."}), 403
```

Di `api_devices()`, tambahkan kolom baru ke query:

```python
            "SELECT ip_address, mac_address, first_seen, last_seen, network, ssid "
            "FROM network_devices ORDER BY last_seen DESC"
```

---

## 5. `main.py`

Ganti blok daftar `devices` (baris 17-26) dengan kode berikut, dan taruh impornya di atas:

```python
from network_info import get_ssid, get_gateway

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
```

Di rumah, kedua router tetap dipantau seperti biasa. Di wifi lain, yang dipantau hanya gateway jaringan itu.

---

## Cara menguji

1. Jalankan perintah SQL di langkah 2.
2. Di rumah, jalankan `python wifi_scanner.py` sebagai **Administrator**. Seharusnya berjalan normal dan datanya tersimpan dengan `ssid` rumahmu.
3. Di wifi lain, jalankan lagi. Yang muncul adalah pesan "belum ada di JARINGAN_DIIZINKAN". Kalau jaringan itu memang boleh kamu pindai, tambahkan pasangan `(network, ssid)`-nya ke daftar, lalu jalankan ulang.

---

## Hal yang perlu diperhatikan

- **SSID tidak terbaca** (hasilnya `kabel/LAN` padahal memakai wifi): di sebagian versi Windows 11, `netsh wlan` butuh **Location services** menyala di pengaturan Windows.
- **Wifi publik** sering mengaktifkan *client isolation*, sehingga scan hanya menemukan router atau tidak menemukan apa pun.
- **Password database** jangan ditulis langsung di `database.py` kalau kode akan dibagikan atau diunggah ke GitHub. Gunakan environment variable:

  ```python
  import os
  # ...
  password=os.getenv("DB_PASSWORD")
  ```

  Kalau password sudah pernah terlihat atau terbagikan, sebaiknya diganti.
- **Bug kecil** di `save_to_database()` dan `api_devices()`: variabel `cursor` dipakai di `finally`, tetapi tidak terdefinisi kalau `get_connection()` gagal (muncul `NameError` yang menutupi error aslinya). Perbaikan: tambahkan `cursor = None` di samping `connection = None`, dan ganti kondisi penutupnya menjadi `if cursor: cursor.close()`.
- **MAC acak** pada HP modern membuat perangkat yang sama bisa tampil dengan MAC berbeda di tiap wifi.

## Langkah berikutnya (opsional)

Menambahkan **notifikasi perangkat baru** (misalnya lewat Telegram). Saat ini `ON DUPLICATE KEY` membuat program tidak bisa membedakan perangkat baru dan lama, jadi `save_to_database()` perlu diubah agar mengecek MAC yang benar-benar baru di jaringan tersebut, dengan mode baseline untuk scan pertama supaya tidak banjir notifikasi.
