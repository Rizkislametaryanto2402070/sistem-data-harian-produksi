"""Isi template Data Harian Produksi (sheet 1) dari data terstruktur.

Template asli dipakai apa adanya; modul ini hanya menulis nilai ke sel.
Berasal dari prototipe `isi_template.py` di project, dengan tambahan:
  - nilai kosong (belum diisi operator) tidak ditulis dan tidak merusak total;
  - header (shift + tanggal) semua 8 formulir selalu diisi, supaya tidak ada
    tanggal lama yang tersisa dari template;
  - nama pemeriksa/penyetuju/operator ditulis di baris nama (baris 30 tiap blok);
  - `isi_semua` mengisi satu workbook penuh untuk satu tanggal + shift.
Modul ini tidak bergantung pada Django.
"""
import openpyxl
import openpyxl.styles

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jum'at", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]

MAKS_BARIS = 12
JARAK_BLOK = 32  # tiap blok formulir berjarak 32 baris

# 8 formulir: blok (0..3), sisi kiri/kanan
KOLOM = {
    "kiri": dict(item="C", jam="D", jam2="E", plan="F", actl="G", ng="H", ket="J",
                 op="B", lbl="G", val="I", setuju="G", periksa="I", operator="K"),
    "kanan": dict(item="N", jam="O", jam2="P", plan="Q", actl="R", ng="S", ket="U",
                  op="M", lbl="R", val="T", setuju="R", periksa="T", operator="V"),
}
MESIN = {"110 Ts A": (0, "kiri"), "110 Ts B": (0, "kanan"),
         "60 Ts A": (1, "kiri"), "60 Ts B": (1, "kanan"),
         "60 Ts C": (2, "kiri"), "60 Ts D": (2, "kanan"),
         "60 Ts E": (3, "kiri"), "60 Ts (cadangan)": (3, "kanan")}


def tgl_id(d):
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"


def jam_id(t):
    """datetime.time -> '07.00' (format penulisan di formulir)."""
    return None if t is None else f"{t.hour:02d}.{t.minute:02d}"


def _tengah(cell):
    cell.alignment = openpyxl.styles.Alignment(
        horizontal="center", vertical="center", shrink_to_fit=True)


def isi_header(ws, mesin, tanggal, shift):
    """Tulis shift dan hari/tanggal sebuah formulir."""
    blok, sisi = MESIN[mesin]
    k = KOLOM[sisi]
    o = blok * JARAK_BLOK
    ws[f"{k['lbl']}{7 + o}"] = "Hari / Tanggal "      # buang teks tanggal basi di sel label
    ws[f"{k['val']}{7 + o}"] = f": {tgl_id(tanggal)}"
    ws[f"{k['val']}{6 + o}"] = f": {shift}"


def isi_tanda(ws, mesin, operator=None, diperiksa=None, disetujui=None):
    """Tulis nama di baris nama bawah APPROVED / CHECKED / Operator."""
    blok, sisi = MESIN[mesin]
    k = KOLOM[sisi]
    r = 30 + blok * JARAK_BLOK
    for kunci, nama in (("setuju", disetujui), ("periksa", diperiksa), ("operator", operator)):
        if nama:
            sel = ws[f"{k[kunci]}{r}"]
            sel.value = nama
            _tengah(sel)


def isi(ws, mesin, tanggal, shift, operator, baris):
    """Isi satu formulir. `baris`: list dict item, mulai, selesai, plan, actl, ng, ket.
    mulai/selesai berupa teks 'HH.MM'; plan/actl/ng boleh None."""
    assert len(baris) <= MAKS_BARIS, f"maks {MAKS_BARIS} baris per formulir"
    blok, sisi = MESIN[mesin]
    k = KOLOM[sisi]
    o = blok * JARAK_BLOK
    isi_header(ws, mesin, tanggal, shift)
    if operator:
        ws[f"{k['op']}{7 + o}"] = f" Operator   : {operator}"
    for i, b in enumerate(baris):
        r = 11 + o + i
        ws[f"{k['item']}{r}"] = b["item"]
        ws[f"{k['jam']}{r}"] = b.get("mulai")
        ws[f"{k['jam2']}{r}"] = b.get("selesai")
        for col in (k["item"], k["jam"], k["jam2"]):    # teks panjang menyusut, tidak menimpa kolom lain
            c = ws[f"{col}{r}"]
            c.alignment = openpyxl.styles.Alignment(
                horizontal=c.alignment.horizontal, vertical="center", shrink_to_fit=True)
        ws[f"{k['plan']}{r}"] = b.get("plan")
        ws[f"{k['actl']}{r}"] = b.get("actl")
        ws[f"{k['ng']}{r}"] = b.get("ng")
        ws[f"{k['ket']}{r}"] = b.get("ket") or None
    rt = 23 + o   # baris Total (F:G digabung = total Actl saja, H = NG)
    ws[f"{k['plan']}{rt}"] = sum(b.get("actl") or 0 for b in baris)
    ws[f"{k['ng']}{rt}"] = sum(b.get("ng") or 0 for b in baris)


def isi_semua(ws, tanggal, shift, data):
    """Isi seluruh 8 formulir untuk satu tanggal + shift.

    `data`: dict kode_mesin -> dict(operator, diperiksa, disetujui, baris=[...]).
    Mesin tanpa data hanya diisi header-nya.
    """
    for mesin in MESIN:
        d = data.get(mesin)
        if d is None:
            isi_header(ws, mesin, tanggal, shift)
            continue
        isi(ws, mesin, tanggal, shift, d.get("operator"), d.get("baris", []))
        isi_tanda(ws, mesin, d.get("operator"), d.get("diperiksa"), d.get("disetujui"))
