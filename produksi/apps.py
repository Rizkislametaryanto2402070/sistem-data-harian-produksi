from django.apps import AppConfig
from django.db.models.signals import post_migrate

# Kode mesin harus sama persis dengan kunci MESIN di isi_template.py.
# Mesin ke-8 tidak ada di lapangan: tersedia, tetapi nonaktif secara default.
DAFTAR_MESIN = [
    ("110 Ts A", 1, True),
    ("110 Ts B", 2, True),
    ("60 Ts A", 3, True),
    ("60 Ts B", 4, True),
    ("60 Ts C", 5, True),
    ("60 Ts D", 6, True),
    ("60 Ts E", 7, True),
    ("60 Ts (cadangan)", 8, False),
]


def isi_mesin_awal(sender, **kwargs):
    """Buat 8 mesin bila belum ada. Aman dijalankan berulang; tidak menimpa perubahan admin."""
    from .models import Mesin
    for kode, urutan, aktif in DAFTAR_MESIN:
        Mesin.objects.get_or_create(kode=kode, defaults={"urutan": urutan, "aktif": aktif})


class ProduksiConfig(AppConfig):
    name = "produksi"
    verbose_name = "Produksi"

    def ready(self):
        post_migrate.connect(isi_mesin_awal, sender=self)
