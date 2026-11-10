"""Ekspor Excel: ambil data dari database lalu isi template asli lewat isi_template."""
from io import BytesIO

import openpyxl
from django.conf import settings

from . import isi_template
from .models import Formulir


def _nama(user):
    return (user.get_full_name() or user.get_username()) if user else None


def kumpulkan_data(tanggal, shift):
    """dict kode_mesin -> data formulir, siap dikirim ke isi_template.isi_semua."""
    data = {}
    formulir = (Formulir.objects.filter(tanggal=tanggal, shift=shift)
                .select_related("mesin", "operator", "pengisi", "diperiksa_oleh", "disetujui_oleh")
                .prefetch_related("baris__item"))
    for f in formulir:
        data[f.mesin.kode] = {
            "operator": f.nama_operator() or None,
            "diperiksa": _nama(f.diperiksa_oleh),
            "disetujui": _nama(f.disetujui_oleh),
            "baris": [{
                "item": b.item.label,
                "mulai": isi_template.jam_id(b.jam_mulai),
                "selesai": isi_template.jam_id(b.jam_selesai),
                "plan": b.plan,
                "actl": b.actual,
                "ng": b.ng,
                "ket": b.keterangan,
            } for b in f.baris.all()],
        }
    return data


def buat_workbook(tanggal, shift):
    wb = openpyxl.load_workbook(settings.TEMPLATE_EXCEL)
    ws = wb.worksheets[0]   # sheet 1 = Data Harian Produksi; sheet lain (jika ada) tidak disentuh
    isi_template.isi_semua(ws, tanggal, shift, kumpulkan_data(tanggal, shift))
    return wb


def buat_xlsx_bytes(tanggal, shift):
    buf = BytesIO()
    buat_workbook(tanggal, shift).save(buf)
    return buf.getvalue()


def nama_file(tanggal, shift):
    return f"Data_Harian_Produksi_{tanggal:%Y-%m-%d}_{shift}.xlsx"
