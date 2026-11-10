"""Bantuan untuk halaman depan Master data (/kelola/): angka ringkasan, jumlah per modul, keterangan modul."""
from collections import Counter

from django import template
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from ..models import Formulir, Item, Mesin, Operator

register = template.Library()

KETERANGAN = {
    "formulir": "Data formulir rencana dan realisasi produksi harian per mesin dan shift.",
    "item": "Katalog item dan nomor part yang dipilih admin saat mengisi plan.",
    "mesin": "Daftar unit mesin produksi. Kode mesin tetap, hanya status aktif yang bisa diubah.",
    "operator": "Daftar nama operator yang dipilih di laptop produksi saat mengisi data.",
    "group": "Pengaturan kelompok hak akses pengguna.",
    "user": "Kelola akun login operator mesin dan administrator.",
}
SATUAN = {"formulir": "data", "item": "part", "mesin": "unit", "operator": "nama", "group": "grup", "user": "akun"}


@register.simple_tag
def ringkasan_master():
    """Angka untuk empat kartu ringkasan dan jumlah per modul."""
    User = get_user_model()
    kode = list(Mesin.objects.filter(aktif=True).values_list("kode", flat=True))
    rincian = Counter(k.split(" Ts")[0] + " Ts" if " Ts" in k else k for k in kode)
    return {
        "formulir": Formulir.objects.count(),
        "item": Item.objects.count(),
        "mesin": Mesin.objects.count(),
        "mesin_aktif": len(kode),
        "mesin_rincian": " · ".join(f"{nama} ({n})" for nama, n in rincian.items()),
        "operator": Operator.objects.count(),
        "user": User.objects.count(),
        "user_aktif": User.objects.filter(is_active=True).count(),
        "group": Group.objects.count(),
    }


@register.filter
def ambil(kamus, kunci):
    return kamus.get(str(kunci).lower(), "")


@register.filter
def keterangan_modul(object_name):
    return KETERANGAN.get(str(object_name).lower(), "")


@register.filter
def satuan_modul(object_name):
    return SATUAN.get(str(object_name).lower(), "data")
