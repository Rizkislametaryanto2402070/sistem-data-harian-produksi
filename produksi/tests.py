"""Tes alur penuh: admin atur plan -> operator isi dan kirim -> admin periksa dan setujui -> ekspor Excel.
Jalankan: python manage.py test"""
import datetime as dt
from io import BytesIO

import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BarisProduksi, Formulir, Item, Mesin, Operator

QS = "?tanggal=2026-11-04&shift=Pagi"
TGL = dt.date(2026, 11, 4)


class AlurProduksiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.admin = U.objects.create_user("admin1", password="rahasia123", is_staff=True, first_name="Siti")
        cls.op = U.objects.create_user("op1", password="rahasia123", first_name="Budi")
        cls.item = Item.objects.create(nama="Bracket A", no_part="12345-01")
        cls.mesin = Mesin.objects.get(kode="110 Ts A")

    def masuk(self, user):
        self.client.force_login(user)

    def atur_plan(self, n=1, plan=800):
        data = {"baris-TOTAL_FORMS": str(n), "baris-INITIAL_FORMS": "0",
                "baris-MIN_NUM_FORMS": "0", "baris-MAX_NUM_FORMS": "12"}
        for i in range(n):
            data[f"baris-{i}-item"] = str(self.item.pk)
            data[f"baris-{i}-plan"] = str(plan)
        return self.client.post(reverse("panel_plan", args=[self.mesin.pk]) + QS, data)

    def isi_operator(self, formulir, kirim=True, actual="780"):
        b = formulir.baris.get()
        data = {"form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(b.pk), "form-0-jam_mulai": "07:00", "form-0-jam_selesai": "11:00",
                "form-0-actual": actual, "form-0-ng": "12", "form-0-keterangan": "Ganti molding"}
        if kirim:
            data["kirim"] = "1"
        return self.client.post(reverse("operator_isi", args=[formulir.pk]), data)

    def test_mesin_awal_8_dan_ke_8_nonaktif(self):
        self.assertEqual(Mesin.objects.count(), 8)
        self.assertEqual(list(Mesin.objects.filter(aktif=False).values_list("kode", flat=True)),
                         ["60 Ts (cadangan)"])

    def test_operator_tidak_boleh_buka_panel_admin(self):
        self.masuk(self.op)
        self.assertEqual(self.client.get(reverse("panel_beranda")).status_code, 403)
        self.assertEqual(self.client.get(reverse("panel_ekspor") + QS).status_code, 403)

    def test_beranda_mengarahkan_sesuai_peran(self):
        self.masuk(self.op)
        self.assertRedirects(self.client.get(reverse("beranda")), reverse("operator_beranda"))
        self.masuk(self.admin)
        self.assertRedirects(self.client.get(reverse("beranda")), reverse("panel_beranda"))

    def test_alur_penuh_sampai_excel(self):
        self.masuk(self.admin)
        self.assertEqual(self.atur_plan().status_code, 302)
        f = Formulir.objects.get(mesin=self.mesin, tanggal=TGL, shift="Pagi")
        self.assertEqual(f.baris.get().urut, 1)
        self.assertEqual(f.status, "Menunggu operator")

        self.masuk(self.op)
        self.assertEqual(self.isi_operator(f).status_code, 302)
        f.refresh_from_db()
        self.assertEqual(f.status, "Perlu disetujui")
        self.assertEqual(f.operator, self.op)

        self.masuk(self.admin)
        self.client.post(reverse("panel_aksi", args=[f.pk]), {"aksi": "setujui"})   # satu klik: Checked + Approved
        f.refresh_from_db()
        self.assertEqual(f.status, "Disetujui")
        self.assertEqual((f.diperiksa_oleh, f.disetujui_oleh), (self.admin, self.admin))

        resp = self.client.get(reverse("panel_ekspor") + QS)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])
        ws = openpyxl.load_workbook(BytesIO(resp.content)).worksheets[0]
        self.assertEqual(ws["C11"].value, "Bracket A / 12345-01")
        self.assertEqual((ws["D11"].value, ws["E11"].value), ("07.00", "11.00"))
        self.assertEqual((ws["F11"].value, ws["G11"].value, ws["H11"].value), (800, 780, 12))
        self.assertEqual(ws["F23"].value, 780)
        self.assertEqual(ws["I7"].value, ": Rabu, 4 November 2026")
        self.assertEqual((ws["G30"].value, ws["I30"].value, ws["K30"].value), ("Siti", "Siti", "Budi"))

    def test_kirim_ditolak_bila_actual_kosong(self):
        self.masuk(self.admin)
        self.atur_plan()
        f = Formulir.objects.get()
        self.masuk(self.op)
        self.isi_operator(f, actual="")
        f.refresh_from_db()
        self.assertIsNone(f.dikirim_at)

    def test_setelah_dikirim_operator_tidak_bisa_ubah(self):
        self.masuk(self.admin)
        self.atur_plan()
        f = Formulir.objects.get()
        self.masuk(self.op)
        self.isi_operator(f)
        self.isi_operator(f, actual="999")
        self.assertEqual(f.baris.get().actual, 780)

    def test_ng_tidak_boleh_melebihi_actual(self):
        self.masuk(self.admin)
        self.atur_plan()
        f = Formulir.objects.get()
        self.masuk(self.op)
        self.isi_operator(f, kirim=False, actual="5")   # ng = 12 > 5
        self.assertIsNone(f.baris.get().actual)

    def test_maksimal_12_baris_per_formulir(self):
        self.masuk(self.admin)
        self.atur_plan(n=13)
        self.assertEqual(BarisProduksi.objects.count(), 0)
        self.atur_plan(n=12)
        self.assertEqual(BarisProduksi.objects.count(), 12)
        self.assertEqual(sorted(BarisProduksi.objects.values_list("urut", flat=True)), list(range(1, 13)))

    def test_setujui_ditolak_bila_belum_dikirim(self):
        self.masuk(self.admin)
        self.atur_plan()
        f = Formulir.objects.get()
        self.client.post(reverse("panel_aksi", args=[f.pk]), {"aksi": "setujui"})
        f.refresh_from_db()
        self.assertIsNone(f.disetujui_at)

    def test_setujui_semua(self):
        self.masuk(self.admin)
        self.atur_plan()
        f = Formulir.objects.get()
        self.masuk(self.op)
        self.isi_operator(f)
        self.masuk(self.admin)
        resp = self.client.post(reverse("panel_setujui_semua") + QS)
        self.assertEqual(resp.status_code, 302)
        f.refresh_from_db()
        self.assertEqual(f.status, "Disetujui")

    def test_salin_plan_dari_hari_sebelumnya(self):
        self.masuk(self.admin)
        self.atur_plan(plan=555)   # plan untuk 2026-11-04
        resp = self.client.post(reverse("panel_salin") + "?tanggal=2026-11-05&shift=Pagi")
        self.assertEqual(resp.status_code, 302)
        besok = Formulir.objects.get(mesin=self.mesin, tanggal=dt.date(2026, 11, 5), shift="Pagi")
        b = besok.baris.get()
        self.assertEqual((b.item, b.plan, b.urut), (self.item, 555, 1))
        self.assertIsNone(b.actual)
        # dijalankan lagi tidak menimpa atau menggandakan
        self.client.post(reverse("panel_salin") + "?tanggal=2026-11-05&shift=Pagi")
        self.assertEqual(besok.baris.count(), 1)

    def test_halaman_utama_terbuka(self):
        self.masuk(self.admin)
        self.atur_plan()
        f = Formulir.objects.get()
        for nama, args in (("panel_beranda", None), ("panel_periksa", [f.pk]),
                           ("panel_plan", [self.mesin.pk])):
            r = self.client.get(reverse(nama, args=args) + QS)
            self.assertEqual(r.status_code, 200, nama)
        self.masuk(self.op)
        self.assertEqual(self.client.get(reverse("operator_beranda") + QS).status_code, 200)
        self.assertEqual(self.client.get(reverse("operator_isi", args=[f.pk])).status_code, 200)

    def test_login_tampil_dan_pesan_salah(self):
        self.client.logout()
        r = self.client.get(reverse("login"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Masuk")
        self.assertContains(r, 'id="pd-logo-vector"')   # logo SVG ikut tampil
        r = self.client.post(reverse("login"), {"username": "op1", "password": "salah"})
        self.assertContains(r, "Nama pengguna atau kata sandi salah.")

    def test_halaman_periksa_menampilkan_total_dan_selisih(self):
        self.masuk(self.admin)
        self.atur_plan(plan=800)
        f = Formulir.objects.get()
        self.masuk(self.op)
        self.isi_operator(f)   # actual 780, ng 12
        self.masuk(self.admin)
        r = self.client.get(reverse("panel_periksa", args=[f.pk]))
        self.assertContains(r, "Selisih Actual dan Plan")
        self.assertEqual((r.context["total_plan"], r.context["total_actual"], r.context["selisih"]),
                         (800, 780, -20))
        self.assertContains(r, "Bracket A")


class MasterDataTampilanTest(TestCase):
    """Halaman depan /kelola/ memakai template admin kustom (desain Master data)."""

    def test_halaman_master_data_dan_daftar(self):
        su = get_user_model().objects.create_superuser("super1", password="rahasia123")
        self.client.force_login(su)
        r = self.client.get(reverse("admin:index"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Master data")
        self.assertContains(r, "Tindakan terbaru")
        self.assertContains(r, "Katalog Item")
        self.assertContains(r, "pd-navbar")
        self.assertEqual(self.client.get(reverse("admin:produksi_item_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:produksi_formulir_add")).status_code, 200)


class LaptopBersamaTest(TestCase):
    """Satu akun operator bersama di laptop; nama operator dipilih dari daftar."""

    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.akun = U.objects.create_user("operator", password="rahasia123")
        cls.admin = U.objects.create_user("admin1", password="rahasia123", is_staff=True)
        cls.item = Item.objects.create(nama="Bracket A", no_part="12345-01")
        cls.mesin = Mesin.objects.get(kode="110 Ts A")
        cls.f = Formulir.objects.create(mesin=cls.mesin, tanggal=TGL, shift="Pagi")
        BarisProduksi.objects.create(formulir=cls.f, urut=1, item=cls.item, plan=800)
        cls.budi = Operator.objects.create(nama="Budi")
        cls.sari = Operator.objects.create(nama="Sari")
        Operator.objects.create(nama="Lama", aktif=False)

    def data_isi(self, **extra):
        b = self.f.baris.get()
        data = {"form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000", "form-0-id": str(b.pk), "form-0-jam_mulai": "07:00",
                "form-0-jam_selesai": "15:00", "form-0-actual": "780", "form-0-ng": "2",
                "form-0-keterangan": ""}
        data.update(extra)
        return data

    def test_pilihan_nama_hanya_operator_aktif(self):
        self.client.force_login(self.akun)
        r = self.client.get(reverse("operator_beranda") + QS)
        self.assertContains(r, "Budi")
        self.assertContains(r, "Sari")
        self.assertNotContains(r, "Lama")

    def test_simpan_ditolak_sebelum_pilih_nama(self):
        self.client.force_login(self.akun)
        r = self.client.post(reverse("operator_isi", args=[self.f.pk]), self.data_isi(simpan="1"))
        self.assertEqual(r.status_code, 200)               # halaman tampil lagi, isian tidak hilang
        self.assertContains(r, 'value="780"')
        self.assertContains(r, "Pilih nama operator dulu")
        self.f.refresh_from_db()
        self.assertIsNone(self.f.pengisi)
        self.assertIsNone(self.f.baris.get().actual)

    def test_pilih_nama_lalu_isi_dan_kirim_tercatat(self):
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_pilih_nama"), {"operator": str(self.budi.pk),
                                                           "next": reverse("operator_beranda")})
        self.client.post(reverse("operator_isi", args=[self.f.pk]), self.data_isi(kirim="1"))
        self.f.refresh_from_db()
        self.assertEqual(self.f.pengisi, self.budi)
        self.assertIsNotNone(self.f.dikirim_at)
        self.assertEqual(self.f.nama_operator(), "Budi")

    def test_nama_operator_masuk_ke_excel(self):
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_pilih_nama"), {"operator": str(self.sari.pk)})
        self.client.post(reverse("operator_isi", args=[self.f.pk]), self.data_isi(kirim="1"))
        from . import exporter
        self.assertEqual(exporter.kumpulkan_data(TGL, "Pagi")["110 Ts A"]["operator"], "Sari")

    def test_tanpa_daftar_nama_tetap_bisa_isi_seperti_biasa(self):
        Operator.objects.all().delete()
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_isi", args=[self.f.pk]), self.data_isi(simpan="1"))
        self.assertEqual(self.f.baris.get().actual, 780)

    def test_redirect_next_tidak_boleh_ke_situs_lain(self):
        self.client.force_login(self.akun)
        r = self.client.post(reverse("operator_pilih_nama"),
                             {"operator": str(self.budi.pk), "next": "https://contoh.jahat/"})
        self.assertEqual(r["Location"], reverse("operator_beranda"))

    def test_admin_melihat_nama_pengisi_dan_master_data(self):
        self.f.pengisi = self.budi
        self.f.save()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("panel_beranda") + QS), "Budi")
        super_admin = get_user_model().objects.create_superuser("super1", password="rahasia123")
        self.client.force_login(super_admin)
        self.assertEqual(self.client.get(reverse("admin:produksi_operator_changelist")).status_code, 200)

    def test_nama_dari_isian_dipakai_walau_sesi_kosong(self):
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_isi", args=[self.f.pk]),
                         self.data_isi(simpan="1", operator=str(self.sari.pk)))
        self.f.refresh_from_db()
        self.assertEqual(self.f.pengisi, self.sari)
        self.assertEqual(self.f.baris.get().actual, 780)

    def test_nama_dikosongkan_setelah_kirim(self):
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_pilih_nama"), {"operator": str(self.budi.pk)})
        self.client.post(reverse("operator_isi", args=[self.f.pk]), self.data_isi(kirim="1"))
        self.assertNotIn("operator_id", self.client.session)
        r = self.client.get(reverse("operator_beranda") + QS)
        self.assertContains(r, "Pilih nama dulu sebelum mengisi data")

    def test_simpan_sementara_tidak_mengosongkan_nama(self):
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_pilih_nama"), {"operator": str(self.budi.pk)})
        self.client.post(reverse("operator_isi", args=[self.f.pk]), self.data_isi(simpan="1"))
        self.assertEqual(self.client.session["operator_id"], self.budi.pk)

    def test_nama_hilang_setelah_10_menit_tidak_aktif(self):
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_pilih_nama"), {"operator": str(self.budi.pk)})
        sesi = self.client.session
        sesi["operator_waktu"] = sesi["operator_waktu"] - 11 * 60
        sesi.save()
        r = self.client.get(reverse("operator_beranda") + QS)
        self.assertContains(r, "Pilih nama dulu sebelum mengisi data")
        self.assertNotIn("operator_id", self.client.session)

    def test_nama_masih_ada_sebelum_10_menit(self):
        self.client.force_login(self.akun)
        self.client.post(reverse("operator_pilih_nama"), {"operator": str(self.budi.pk)})
        sesi = self.client.session
        sesi["operator_waktu"] = sesi["operator_waktu"] - 5 * 60
        sesi.save()
        r = self.client.get(reverse("operator_beranda") + QS)
        self.assertNotContains(r, "Pilih nama dulu sebelum mengisi data")


class DataContohTest(TestCase):
    """Perintah isi_data_contoh untuk demo dan portofolio."""

    def jalankan(self, *args):
        from io import StringIO
        from django.core.management import call_command
        call_command("isi_data_contoh", *args, stdout=StringIO())

    def test_membuat_data_dengan_berbagai_status(self):
        self.jalankan()
        status = {f.status for f in Formulir.objects.all()}
        self.assertEqual(status, {"Disetujui", "Perlu disetujui", "Menunggu operator"})
        self.assertGreaterEqual(Item.objects.count(), 8)
        self.assertEqual(Operator.objects.count(), 4)
        self.assertTrue(get_user_model().objects.get(username="admin").is_staff)
        self.assertFalse(get_user_model().objects.get(username="operator").is_staff)

    def test_aman_dijalankan_berulang(self):
        self.jalankan()
        jumlah = (Formulir.objects.count(), BarisProduksi.objects.count(), Item.objects.count())
        self.jalankan()
        self.assertEqual((Formulir.objects.count(), BarisProduksi.objects.count(), Item.objects.count()), jumlah)

    def test_tanpa_akun(self):
        self.jalankan("--tanpa-akun")
        self.assertFalse(get_user_model().objects.filter(username="admin").exists())
