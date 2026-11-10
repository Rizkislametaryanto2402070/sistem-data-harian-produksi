# Sistem Data Harian Produksi

Aplikasi web untuk menggantikan pencatatan data harian produksi yang tadinya ditulis tangan dan dicetak tiap hari.
Operator mengisi data di layar, admin mengatur plan, memeriksa dan menyetujui, lalu mengunduh hasilnya sebagai
**file Excel yang mengikuti tata letak formulir asli**.

Dibuat sebagai proyek magang (MBKM) untuk lingkungan pabrik manufaktur. Nama perusahaan, logo, template asli, dan
seluruh data sudah diganti dengan contoh, sehingga repositori ini aman dipelajari dan dicoba.

<!-- Tambahkan tangkapan layar setelah dibuat (lihat PERIKSA-SEBELUM-PUSH.md), lalu hapus tanda komentar ini:
![Ringkasan admin](docs/screenshots/ringkasan-admin.png)
![Pilih mesin (operator)](docs/screenshots/pilih-mesin.png)
-->

## Masalah dan solusi

| Sebelumnya | Sekarang |
| --- | --- |
| Formulir dicetak dan diisi tangan tiap shift, boros kertas dan waktu admin | Diisi langsung di layar, tanpa cetak |
| Plan ditulis ulang tiap hari | Admin memilih item dari daftar, atau menyalin plan hari sebelumnya |
| Persetujuan dengan tanda tangan basah | Pemeriksaan dan persetujuan digital oleh admin, tercatat siapa dan kapan |
| Rekap manual ke Excel | Satu klik unduh Excel berisi seluruh formulir untuk tanggal dan shift terpilih |

## Fitur

- **Dua peran:** admin (staf) dan operator (akun biasa), dengan halaman dan hak akses terpisah.
- **Alur status satu arah:** Belum ada plan → Menunggu operator → Perlu disetujui → Disetujui. Data yang sudah
  dikirim terkunci; admin dapat mengembalikannya ke operator bila ada koreksi.
- **Maksimal 12 baris per mesin per shift**, divalidasi di aplikasi dan di database.
- **Mode laptop bersama:** satu akun operator di komputer produksi, operator memilih namanya dari daftar. Nama
  dikosongkan otomatis setelah kirim atau 10 menit tanpa aktivitas, dan tercatat di formulir dan di Excel.
- **Ekspor Excel** yang mengisi template apa adanya (OpenPyXL), hanya sel nilai yang ditulis.
- **Tampilan responsif tanpa CDN:** CSS biasa, tanpa framework, tanpa font atau ikon dari internet, jadi tetap
  normal bila jaringan putus. Tabel berubah menjadi kartu di layar kecil.
- **Master data** (item, operator, mesin, akun) lewat halaman admin Django yang sudah ditata ulang.
- **Uji otomatis** untuk model, alur status, hak akses, ekspor, dan mode laptop bersama.

## Teknologi

Django 5.2 (LTS), SQLite, OpenPyXL, Pillow. HTML dan CSS biasa dengan sedikit JavaScript untuk filter dan
pencarian. Tanpa REST API: aplikasi web full-stack bergaya server-rendered.

## Coba sekarang

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations produksi   # lewati bila folder produksi/migrations sudah ada
python manage.py migrate                   # sekaligus membuat 8 mesin
python manage.py isi_data_contoh           # item, nama operator, akun demo, dan formulir hari ini
python manage.py runserver
```

Buka http://127.0.0.1:8000/ lalu masuk dengan akun demo (hanya untuk uji coba lokal):

| Peran | Username | Sandi |
| --- | --- | --- |
| Admin | `admin` | `admin12345` |
| Operator | `operator` | `operator12345` |

Mulai dari admin untuk melihat Ringkasan produksi dan Master data (`/kelola/`), lalu masuk sebagai operator,
pilih nama, dan isi satu mesin. Jalankan tes dengan `python manage.py test`.

**Jangan memakai akun demo ini di server sungguhan.** Untuk dipakai sungguhan, buat akun lewat
`python manage.py createsuperuser` dan atur `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`,
serta `DJANGO_CSRF_ORIGINS` sebagai variabel lingkungan (lihat `config/settings.py`).

## Alur harian

1. Admin: **Ringkasan** → **Isi plan** per mesin (pilih item, isi Plan), atau **Salin plan dari hari sebelumnya**.
2. Operator: pilih nama dan mesin → isi jam, Actual, NG, keterangan → **Simpan dan kirim ke admin**.
3. Admin: **Periksa dan setujui** (satuan atau semua yang sudah dikirim). Koreksi: **Kembalikan ke operator**.
4. Admin: **Unduh Excel** untuk tanggal dan shift tersebut.

## Struktur

```
config/                    pengaturan dan URL proyek
produksi/models.py         Mesin, Item, Operator, Formulir, BarisProduksi (status diturunkan dari kolom waktu)
produksi/views.py          halaman admin (panel) dan operator
produksi/isi_template.py   mengisi template Excel, tanpa ketergantungan Django (dites terpisah)
produksi/exporter.py       menyusun data formulir untuk ekspor
produksi/templates/        HTML
produksi/static/produksi/  CSS
produksi/management/       perintah isi_data_contoh dan import_item
produksi/tests.py          uji Django; test_isi_template.py menguji pengisi Excel
```

## Keputusan rancangan dan batasannya

- **SQLite** dipilih agar mudah dipasang dan dicadangkan (satu file). Cocok untuk beberapa pemakai bersamaan,
  bukan untuk beban besar.
- **Nama operator di laptop bersama dipilih tanpa PIN**: cukup untuk mencatat siapa yang mengisi, tetapi bukan
  bukti identitas. Bila dibutuhkan, PIN pendek per operator bisa ditambahkan.
- **Kode mesin tetap** karena dipakai memetakan formulir ke posisi sel di template Excel.
- **Template Excel di repositori ini adalah contoh netral.** Untuk memakai formulir sendiri, timpa
  `produksi/excel_template/template_data_harian.xlsx` dengan tata letak sel yang sama.

## Lisensi

MIT, lihat `LICENSE`.
