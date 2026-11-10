"""Tes isi_template tanpa Django: hanya butuh openpyxl dan Pillow."""
import datetime as dt
import unittest
from pathlib import Path

import openpyxl

from produksi import isi_template as t

TEMPLATE = Path(__file__).parent / "excel_template" / "template_data_harian.xlsx"
TGL = dt.date(2026, 11, 4)   # Rabu


def baris(n, actl=90, ng=1):
    return [dict(item=f"Item {i} / 1000{i}", mulai="07.00", selesai="08.00",
                 plan=100, actl=actl, ng=ng, ket="") for i in range(1, n + 1)]


class IsiTemplateTest(unittest.TestCase):
    def setUp(self):
        self.wb = openpyxl.load_workbook(TEMPLATE)
        self.ws = self.wb.worksheets[0]

    def test_semua_header_terisi_dan_tidak_ada_tanggal_basi(self):
        t.isi_semua(self.ws, TGL, "Malam", {})
        for blok in range(4):
            o = blok * 32
            for kol_lbl, kol_val in (("G", "I"), ("R", "T")):
                self.assertEqual(self.ws[f"{kol_lbl}{7 + o}"].value, "Hari / Tanggal ")
                self.assertEqual(self.ws[f"{kol_val}{7 + o}"].value, ": Rabu, 4 November 2026")
                self.assertEqual(self.ws[f"{kol_val}{6 + o}"].value, ": Malam")

    def test_total_hanya_actual_dan_nilai_kosong_aman(self):
        b = baris(3)
        b[1]["actl"] = None
        b[1]["ng"] = None
        t.isi_semua(self.ws, TGL, "Pagi", {"110 Ts A": dict(operator="Budi", baris=b)})
        self.assertEqual(self.ws["F23"].value, 180)   # Plan/Actl digabung = total Actl
        self.assertEqual(self.ws["H23"].value, 2)
        self.assertIsNone(self.ws["G12"].value)

    def test_letak_mesin_di_blok_dan_sisi_yang_benar(self):
        t.isi_semua(self.ws, TGL, "Pagi", {
            "60 Ts (cadangan)": dict(operator="Cadang", baris=baris(1)),
            "60 Ts C": dict(operator="C", baris=baris(1)),
        })
        self.assertEqual(self.ws["N107"].value, "Item 1 / 10001")    # blok 3, kanan, baris 11+96
        self.assertEqual(self.ws["C75"].value, "Item 1 / 10001")     # blok 2, kiri, baris 11+64

    def test_maksimal_12_baris(self):
        t.isi_semua(self.ws, TGL, "Pagi", {"60 Ts A": dict(baris=baris(12))})
        with self.assertRaises(AssertionError):
            t.isi_semua(self.ws, TGL, "Pagi", {"60 Ts A": dict(baris=baris(13))})

    def test_nama_di_baris_tanda(self):
        t.isi_semua(self.ws, TGL, "Pagi", {"110 Ts B": dict(
            operator="Op", diperiksa="Adm", disetujui="Adm2", baris=baris(1))})
        self.assertEqual((self.ws["R30"].value, self.ws["T30"].value, self.ws["V30"].value),
                         ("Adm2", "Adm", "Op"))

    def test_sheet_dan_logo_utuh(self):
        t.isi_semua(self.ws, TGL, "Pagi", {})
        self.assertEqual(self.wb.sheetnames, ["110 A, B (PAGI MALAM)"])
        asli = openpyxl.load_workbook(TEMPLATE).worksheets[0]
        self.assertEqual(len(self.ws._images), len(asli._images))
        self.assertGreater(len(self.ws._images), 0)


if __name__ == "__main__":
    unittest.main()
