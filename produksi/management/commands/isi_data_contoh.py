"""Isi data contoh agar tampilan dan alur sistem bisa langsung dicoba (untuk demo dan portofolio).

Membuat: daftar item, daftar nama operator, akun demo (admin dan operator), dan formulir hari ini
dengan berbagai status. Aman dijalankan berulang: data yang sudah ada tidak digandakan.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from produksi.models import BarisProduksi, Formulir, Item, Mesin, Operator

ITEM = [
    ("Bracket A", "DEMO-001"), ("Bracket B", "DEMO-002"), ("Housing Kecil", "DEMO-010"),
    ("Housing Besar", "DEMO-011"), ("Cover Atas", "DEMO-020"), ("Cover Bawah", "DEMO-021"),
    ("Knob Putar", "DEMO-030"), ("Klip Plastik", "DEMO-040"),
]
OPERATOR = ["Operator Contoh 1", "Operator Contoh 2", "Operator Contoh 3", "Operator Contoh 4"]
JAM = [(dt.time(7, 0), dt.time(9, 30)), (dt.time(9, 45), dt.time(12, 0)),
       (dt.time(13, 0), dt.time(15, 0)), (dt.time(15, 15), dt.time(16, 0))]


class Command(BaseCommand):
    help = "Isi data contoh (item, nama operator, akun demo, dan formulir hari ini)."

    def add_arguments(self, parser):
        parser.add_argument("--tanpa-akun", action="store_true",
                            help="Jangan buat akun demo (admin dan operator).")

    def handle(self, *args, **opts):
        mesin = list(Mesin.objects.filter(aktif=True))
        if len(mesin) < 4:
            raise CommandError("Mesin belum ada. Jalankan 'python manage.py migrate' dulu.")

        item = [Item.objects.get_or_create(nama=n, no_part=p)[0] for n, p in ITEM]
        nama = [Operator.objects.get_or_create(nama=n)[0] for n in OPERATOR]

        admin = None
        if not opts["tanpa_akun"]:
            admin = self.akun("admin", "admin12345", staf=True)
            self.akun("operator", "operator12345", staf=False)

        hari_ini = timezone.localdate()
        # Mesin 1 disetujui, 2 menunggu persetujuan, 3 baru ada plan, 4 sedang diisi, sisanya kosong.
        skenario = ["disetujui", "dikirim", "plan", "sebagian"]
        dibuat = 0
        for urutan, (m, kondisi) in enumerate(zip(mesin, skenario)):
            f, baru = Formulir.objects.get_or_create(mesin=m, tanggal=hari_ini, shift="Pagi")
            if f.baris.exists():
                continue
            jumlah = 3 + urutan % 2
            for i in range(jumlah):
                mulai, selesai = JAM[i]
                isi = kondisi in ("disetujui", "dikirim") or (kondisi == "sebagian" and i == 0)
                BarisProduksi.objects.create(
                    formulir=f, urut=i + 1, item=item[(urutan * 2 + i) % len(item)],
                    plan=400 + 100 * i,
                    jam_mulai=mulai if isi else None, jam_selesai=selesai if isi else None,
                    actual=380 + 90 * i if isi else None, ng=(i % 3) if isi else None)
            if kondisi in ("disetujui", "dikirim", "sebagian"):
                f.pengisi = nama[urutan % len(nama)]
            if kondisi in ("disetujui", "dikirim"):
                f.dikirim_at = timezone.now()
            f.save()
            if kondisi == "disetujui" and admin:
                f.setujui(admin)
            dibuat += 1

        self.stdout.write(self.style.SUCCESS(
            f"Data contoh siap: {len(item)} item, {len(nama)} nama operator, "
            f"{dibuat} formulir baru untuk {hari_ini:%d/%m/%Y} shift Pagi."))
        if not opts["tanpa_akun"]:
            self.stdout.write("Akun demo (khusus uji coba lokal): admin / admin12345, operator / operator12345")

    def akun(self, username, sandi, staf):
        User = get_user_model()
        u, baru = User.objects.get_or_create(username=username)
        if baru:
            u.set_password(sandi)
            u.is_staff = u.is_superuser = staf
            u.save()
        return u
