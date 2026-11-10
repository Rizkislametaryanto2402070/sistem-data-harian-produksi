from datetime import timedelta
from functools import wraps
from time import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import exporter
from .forms import BarisOperatorFormSet, BarisPlanFormSet, PilihHariShiftForm
from .models import MAKS_BARIS, BarisProduksi, Formulir, Mesin, Operator, Shift


# ---- Bantuan -------------------------------------------------------------------------------

def admin_required(view):
    """Hanya admin (is_staff). Operator yang mencoba membuka halaman ini mendapat 403."""
    @login_required
    @wraps(view)
    def dibungkus(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return dibungkus


def shift_bawaan():
    return (Shift.PAGI if 6 <= timezone.localtime().hour < 18 else Shift.MALAM).value


def hari_shift(request):
    """Tanggal + shift dari query string (?tanggal=YYYY-MM-DD&shift=Pagi); bawaan: hari ini."""
    form = PilihHariShiftForm(request.GET or None)
    if form.is_valid():
        return form.cleaned_data["tanggal"], form.cleaned_data["shift"]
    return timezone.localdate(), shift_bawaan()


def konteks_hari(tanggal, shift):
    return {
        "tanggal": tanggal,
        "shift": shift,
        "pilih": PilihHariShiftForm(initial={"tanggal": tanggal, "shift": shift}),
        "qs": f"tanggal={tanggal.isoformat()}&shift={shift}",
        "kemarin": tanggal - timedelta(days=1),
        "besok": tanggal + timedelta(days=1),
        "hari_ini": timezone.localdate(),
    }


def url_dengan(nama, tanggal, shift, **kwargs):
    return f"{reverse(nama, kwargs=kwargs or None)}?tanggal={tanggal.isoformat()}&shift={shift}"


@login_required
def beranda(request):
    return redirect("panel_beranda" if request.user.is_staff else "operator_beranda")


# ---- Operator ------------------------------------------------------------------------------

KUNCI_OPERATOR = "operator_id"
KUNCI_WAKTU = "operator_waktu"


def batas_diam():
    """Detik tanpa aktivitas sebelum nama operator dikosongkan (bawaan 10 menit)."""
    return getattr(settings, "OPERATOR_DIAM_DETIK", 600)


def simpan_pilihan(request, operator):
    request.session[KUNCI_OPERATOR] = operator.pk
    request.session[KUNCI_WAKTU] = time()


def kosongkan_pilihan(request):
    request.session.pop(KUNCI_OPERATOR, None)
    request.session.pop(KUNCI_WAKTU, None)


def operator_terpilih(request):
    """Operator yang dipilih di laptop ini, atau None bila belum dipilih, nonaktif, atau sudah
    lama tidak dipakai (lewat batas_diam). Tiap pemakaian memperpanjang waktunya."""
    pk = request.session.get(KUNCI_OPERATOR)
    if not pk:
        return None
    if time() - request.session.get(KUNCI_WAKTU, 0) > batas_diam():
        kosongkan_pilihan(request)
        return None
    op = Operator.objects.filter(pk=pk, aktif=True).first()
    if op is None:
        kosongkan_pilihan(request)
        return None
    request.session[KUNCI_WAKTU] = time()
    return op


def operator_dari_isian(request):
    """Nama yang dikirim bersama formulir (kolom 'operator'); bila tidak ada, pakai pilihan sesi."""
    if "operator" in request.POST:
        op = Operator.objects.filter(pk=request.POST.get("operator") or 0, aktif=True).first()
        if op:
            simpan_pilihan(request, op)
        return op
    return operator_terpilih(request)


def konteks_operator(request, terpilih=None, dari_isian=False):
    """dari_isian=True: pakai 'terpilih' apa adanya (nama dari kolom formulir yang baru dikirim)."""
    daftar = list(Operator.objects.filter(aktif=True))
    if not dari_isian:
        terpilih = terpilih or operator_terpilih(request)
    return {"daftar_operator": daftar, "operator_dipilih": terpilih,
            "wajib_pilih_nama": bool(daftar) and terpilih is None}


@login_required
@require_POST
def operator_pilih_nama(request):
    """Simpan nama operator yang dipilih. Kosong = hapus pilihan."""
    pk = request.POST.get("operator", "")
    if pk:
        pilih = Operator.objects.filter(pk=pk, aktif=True).first()
        if pilih:
            simpan_pilihan(request, pilih)
        else:
            messages.error(request, "Nama operator tidak ditemukan.")
    else:
        kosongkan_pilihan(request)
    tujuan = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(tujuan, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        tujuan = reverse("operator_beranda")
    return redirect(tujuan)


@login_required
def operator_beranda(request):
    tanggal, shift = hari_shift(request)
    ada = {f.mesin_id: f for f in
           Formulir.objects.filter(tanggal=tanggal, shift=shift).prefetch_related("baris")}
    kartu = [{"mesin": m, "formulir": ada.get(m.id)} for m in Mesin.objects.filter(aktif=True)]
    return render(request, "produksi/operator_beranda.html",
                  {**konteks_hari(tanggal, shift), **konteks_operator(request), "kartu": kartu})


@login_required
def operator_isi(request, pk):
    f = get_object_or_404(Formulir.objects.select_related("mesin", "operator", "pengisi"), pk=pk)
    kembali = url_dengan("operator_beranda", f.tanggal, f.shift)
    qs = f.baris.select_related("item")
    if not qs.exists():
        messages.error(request, "Admin belum mengisi item dan plan untuk mesin ini.")
        return redirect(kembali)

    boleh = f.operator_bisa_ubah
    nama_dipilih = None
    if request.method == "POST":
        if not boleh:
            messages.error(request, "Formulir sudah dikirim dan tidak bisa diubah. Minta admin membukanya kembali.")
            return redirect(request.path)
        formset = BarisOperatorFormSet(request.POST, queryset=qs)
        nama_dipilih = operator_dari_isian(request)
        if konteks_operator(request, nama_dipilih, dari_isian=True)["wajib_pilih_nama"]:
            # Tidak redirect: isian operator tetap tampil, tinggal memilih nama lalu menyimpan lagi.
            messages.error(request, "Pilih nama operator dulu, lalu tekan Simpan atau Kirim lagi. "
                                    "Isian Anda belum hilang.")
        elif formset.is_valid():
            with transaction.atomic():
                formset.save()
                f.operator = request.user
                f.pengisi = nama_dipilih or f.pengisi
                f.save(update_fields=["operator", "pengisi"])
            if "kirim" in request.POST:
                belum = [str(b.urut) for b in f.baris.all() if not b.lengkap]
                if belum:
                    messages.error(request, "Data tersimpan, tetapi belum bisa dikirim. Lengkapi jam mulai, "
                                            "jam selesai, dan Actual pada baris: " + ", ".join(belum) + ".")
                    return redirect(request.path)
                f.baris.filter(ng__isnull=True).update(ng=0)   # NG kosong dianggap 0
                f.dikirim_at = timezone.now()
                f.save(update_fields=["dikirim_at"])
                pesan = f"Formulir {f.mesin} sudah terkirim ke admin."
                if nama_dipilih:
                    kosongkan_pilihan(request)   # operator berikutnya wajib memilih namanya sendiri
                    pesan += " Nama operator dikosongkan; pilih nama Anda untuk mesin berikutnya."
                messages.success(request, pesan)
                return redirect(kembali)
            messages.success(request, "Data tersimpan. Anda bisa melanjutkannya nanti.")
            return redirect(request.path)
    else:
        formset = BarisOperatorFormSet(queryset=qs)
    info_operator = konteks_operator(request, nama_dipilih, dari_isian=request.method == "POST")

    if not boleh:
        for form in formset:
            for field in form.fields.values():
                field.disabled = True
    return render(request, "produksi/operator_isi.html", {
        **info_operator, "f": f, "formset": formset, "boleh": boleh, "kembali": kembali,
        "jumlah_baris": f.jumlah_baris(), "jumlah_terisi": f.jumlah_terisi(),
    })


# ---- Admin ---------------------------------------------------------------------------------

@admin_required
def panel_beranda(request):
    tanggal, shift = hari_shift(request)
    ada = {f.mesin_id: f for f in Formulir.objects.filter(tanggal=tanggal, shift=shift)
           .select_related("operator", "pengisi").prefetch_related("baris")}
    baris = []
    hitung = {"belum": 0, "menunggu": 0, "perlu": 0, "selesai": 0}
    for m in Mesin.objects.all():
        f = ada.get(m.id)
        if not m.aktif and f is None:
            continue   # mesin nonaktif disembunyikan kecuali sudah punya formulir
        status = f.status if f else "Belum ada plan"
        url_plan = url_dengan("panel_plan", tanggal, shift, mesin_id=m.pk)
        if status == "Belum ada plan":
            hitung["belum"] += 1
            aksi = {"label": "Isi plan", "url": url_plan, "primer": True}
        elif status == "Menunggu operator":
            hitung["menunggu"] += 1
            aksi = {"label": "Ubah plan", "url": url_plan, "primer": False}
        elif status == "Perlu disetujui":
            hitung["perlu"] += 1
            aksi = {"label": "Periksa dan setujui", "url": reverse("panel_periksa", args=[f.pk]), "primer": True}
        else:
            hitung["selesai"] += 1
            aksi = {"label": "Lihat", "url": reverse("panel_periksa", args=[f.pk]), "primer": False}
        baris.append({"mesin": m, "formulir": f, "status": status, "aksi": aksi})
    return render(request, "produksi/panel_beranda.html",
                  {**konteks_hari(tanggal, shift), "baris": baris, "hitung": hitung})


def simpan_plan(formset, formulir):
    """Simpan item+plan; baris baru mendapat nomor urut kosong terkecil (1..12)."""
    instances = formset.save(commit=False)
    for obj in formset.deleted_objects:
        obj.delete()
    terpakai = set(formulir.baris.values_list("urut", flat=True))
    for inst in instances:
        if inst.pk is None:
            inst.formulir = formulir
            inst.urut = next(u for u in range(1, MAKS_BARIS + 1) if u not in terpakai)
            terpakai.add(inst.urut)
        inst.save()


@admin_required
def panel_plan(request, mesin_id):
    mesin = get_object_or_404(Mesin, pk=mesin_id)
    tanggal, shift = hari_shift(request)
    f, _ = Formulir.objects.get_or_create(mesin=mesin, tanggal=tanggal, shift=shift)
    kembali = url_dengan("panel_beranda", tanggal, shift)
    if not f.plan_bisa_ubah:
        messages.error(request, "Formulir sudah disetujui. Kembalikan ke operator dulu bila plan perlu diubah.")
        return redirect("panel_periksa", pk=f.pk)

    formset = BarisPlanFormSet(request.POST or None, instance=f)
    if request.method == "POST" and formset.is_valid():
        with transaction.atomic():
            simpan_plan(formset, f)
        messages.success(request, f"Plan {mesin} disimpan.")
        return redirect(kembali)
    return render(request, "produksi/panel_plan.html",
                  {**konteks_hari(tanggal, shift), "mesin": mesin, "f": f, "formset": formset, "kembali": kembali})


@admin_required
@require_POST
def panel_salin(request):
    """Salin item + plan dari hari sebelumnya (shift sama) ke mesin yang belum punya plan."""
    tanggal, shift = hari_shift(request)
    sumber = (Formulir.objects.filter(tanggal=tanggal - timedelta(days=1), shift=shift, mesin__aktif=True)
              .select_related("mesin").prefetch_related("baris"))
    disalin = 0
    with transaction.atomic():
        for s in sumber:
            if not s.baris.all():
                continue
            f, _ = Formulir.objects.get_or_create(mesin=s.mesin, tanggal=tanggal, shift=shift)
            if f.baris.exists():
                continue
            BarisProduksi.objects.bulk_create([
                BarisProduksi(formulir=f, urut=b.urut, item_id=b.item_id, plan=b.plan) for b in s.baris.all()])
            disalin += 1
    if disalin:
        messages.success(request, f"Plan disalin dari hari sebelumnya untuk {disalin} mesin. "
                                  "Cek dan ubah bila perlu.")
    else:
        messages.error(request, "Tidak ada plan yang bisa disalin. Hari sebelumnya kosong, "
                                "atau semua mesin sudah punya plan.")
    return redirect(url_dengan("panel_beranda", tanggal, shift))


@admin_required
@require_POST
def panel_setujui_semua(request):
    """Setujui sekaligus semua formulir yang sudah dikirim operator untuk tanggal + shift ini."""
    tanggal, shift = hari_shift(request)
    n = 0
    with transaction.atomic():
        for f in Formulir.objects.filter(tanggal=tanggal, shift=shift,
                                         dikirim_at__isnull=False, disetujui_at__isnull=True):
            f.setujui(request.user)
            n += 1
    if n:
        messages.success(request, f"{n} formulir disetujui.")
    else:
        messages.error(request, "Tidak ada formulir yang menunggu persetujuan.")
    return redirect(url_dengan("panel_beranda", tanggal, shift))


@admin_required
def panel_periksa(request, pk):
    f = get_object_or_404(Formulir.objects.select_related(
        "mesin", "operator", "pengisi", "diperiksa_oleh", "disetujui_oleh").prefetch_related("baris__item"), pk=pk)
    total_plan = sum(b.plan for b in f.baris.all())
    total_actual = f.total_actual()
    selisih = total_actual - total_plan
    persen = round(selisih / total_plan * 100) if total_plan else 0
    return render(request, "produksi/panel_periksa.html", {
        "f": f,
        "baris": f.baris.all(),
        "total_plan": total_plan,
        "total_actual": total_actual,
        "selisih": selisih,
        "persen": persen,
        "total_ng": f.total_ng(),
        "kembali": url_dengan("panel_beranda", f.tanggal, f.shift),
        "plan_url": url_dengan("panel_plan", f.tanggal, f.shift, mesin_id=f.mesin_id),
    })


@admin_required
@require_POST
def panel_aksi(request, pk):
    f = get_object_or_404(Formulir, pk=pk)
    aksi = request.POST.get("aksi")
    if aksi == "setujui":
        if not f.dikirim_at:
            messages.error(request, "Operator belum mengirim formulir ini.")
        elif f.disetujui_at:
            messages.error(request, "Formulir sudah disetujui.")
        else:
            f.setujui(request.user)
            messages.success(request, f"Formulir {f.mesin} disetujui.")
            return redirect(url_dengan("panel_beranda", f.tanggal, f.shift))
    elif aksi == "buka":
        f.buka_kembali()
        messages.success(request, "Formulir dikembalikan ke operator untuk diperbaiki.")
    else:
        messages.error(request, "Aksi tidak dikenal.")
    return redirect("panel_periksa", pk=f.pk)


@admin_required
def panel_ekspor(request):
    tanggal, shift = hari_shift(request)
    isi = exporter.buat_xlsx_bytes(tanggal, shift)
    respons = HttpResponse(
        isi, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respons["Content-Disposition"] = f'attachment; filename="{exporter.nama_file(tanggal, shift)}"'
    return respons
