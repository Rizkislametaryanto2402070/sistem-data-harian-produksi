from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

MAKS_BARIS = 12  # sesuai template: 12 baris per formulir


class Shift(models.TextChoices):
    PAGI = "Pagi", "Pagi"
    MALAM = "Malam", "Malam"


class Mesin(models.Model):
    kode = models.CharField("Mesin", max_length=40, unique=True)
    urutan = models.PositiveSmallIntegerField(unique=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["urutan"]
        verbose_name = "mesin"
        verbose_name_plural = "mesin"

    def __str__(self):
        return self.kode


class Item(models.Model):
    """Daftar pilihan item/part. Diisi admin; operator tidak mengetik item."""
    nama = models.CharField(max_length=120)
    no_part = models.CharField("No. Part", max_length=60, blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nama", "no_part"]
        constraints = [models.UniqueConstraint(fields=["nama", "no_part"], name="item_nama_nopart_unik")]

    @property
    def label(self):
        return f"{self.nama} / {self.no_part}" if self.no_part else self.nama

    def __str__(self):
        return self.label


class Operator(models.Model):
    """Daftar nama operator. Laptop produksi login dengan satu akun bersama; siapa yang mengisi
    dicatat dari nama yang dipilih di sini (tanpa PIN)."""
    nama = models.CharField(max_length=80, unique=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nama"]
        verbose_name = "operator"
        verbose_name_plural = "operator"

    def __str__(self):
        return self.nama


class Formulir(models.Model):
    """Satu formulir = satu mesin, satu tanggal, satu shift."""
    mesin = models.ForeignKey(Mesin, on_delete=models.PROTECT, related_name="formulir")
    tanggal = models.DateField()
    shift = models.CharField(max_length=5, choices=Shift.choices)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="formulir_diisi")
    pengisi = models.ForeignKey(Operator, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="formulir_diisi_nama", verbose_name="diisi oleh")
    dikirim_at = models.DateTimeField(null=True, blank=True)
    diperiksa_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="formulir_diperiksa")
    diperiksa_at = models.DateTimeField(null=True, blank=True)
    disetujui_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="formulir_disetujui")
    disetujui_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["tanggal", "mesin__urutan"]
        constraints = [models.UniqueConstraint(fields=["mesin", "tanggal", "shift"], name="formulir_unik")]

    def __str__(self):
        return f"{self.mesin} · {self.tanggal:%d/%m/%Y} · {self.shift}"

    # ---- Status -------------------------------------------------------------------------
    # Empat status saja: Belum ada plan -> Menunggu operator -> Perlu disetujui -> Disetujui.
    # (Checked dan Approved dicatat bersamaan saat admin menyetujui.)

    @property
    def status(self):
        if self.disetujui_at:
            return "Disetujui"
        if self.dikirim_at:
            return "Perlu disetujui"
        if self.jumlah_baris():
            return "Menunggu operator"
        return "Belum ada plan"

    @property
    def status_operator(self):
        """Sebutan status untuk operator."""
        if self.disetujui_at:
            return "Disetujui"
        if self.dikirim_at:
            return "Terkirim"
        if not self.jumlah_baris():
            return "Menunggu admin"
        return "Sedang diisi" if self.jumlah_terisi() else "Siap diisi"

    @property
    def operator_bisa_ubah(self):
        return self.dikirim_at is None

    @property
    def plan_bisa_ubah(self):
        return self.disetujui_at is None

    # Memakai .all() agar memanfaatkan prefetch_related("baris") bila ada.
    def jumlah_baris(self):
        return len(self.baris.all())

    def jumlah_terisi(self):
        return sum(1 for b in self.baris.all() if b.lengkap)

    def total_actual(self):
        return sum(b.actual or 0 for b in self.baris.all())

    def total_ng(self):
        return sum(b.ng or 0 for b in self.baris.all())

    def nama_operator(self):
        """Nama operator yang dipilih (laptop bersama); bila kosong, nama akun yang login."""
        if self.pengisi:
            return self.pengisi.nama
        if not self.operator:
            return ""
        return self.operator.get_full_name() or self.operator.get_username()

    def setujui(self, user, waktu=None):
        """Checked + Approved sekaligus oleh admin. Hanya untuk formulir yang sudah dikirim."""
        waktu = waktu or timezone.now()
        if not self.diperiksa_at:
            self.diperiksa_oleh, self.diperiksa_at = user, waktu
        self.disetujui_oleh, self.disetujui_at = user, waktu
        self.save()

    def buka_kembali(self):
        """Kembalikan ke operator: hapus status kirim, periksa, dan setuju."""
        self.dikirim_at = None
        self.diperiksa_oleh = self.diperiksa_at = None
        self.disetujui_oleh = self.disetujui_at = None
        self.save()


class BarisProduksi(models.Model):
    """Item + plan diisi admin; jam, actual, NG, keterangan diisi operator."""
    formulir = models.ForeignKey(Formulir, on_delete=models.CASCADE, related_name="baris")
    urut = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAKS_BARIS)])
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    plan = models.PositiveIntegerField(default=0)
    jam_mulai = models.TimeField(null=True, blank=True)
    jam_selesai = models.TimeField(null=True, blank=True)
    actual = models.PositiveIntegerField(null=True, blank=True)
    ng = models.PositiveIntegerField("NG", null=True, blank=True)
    keterangan = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["urut"]
        constraints = [
            models.UniqueConstraint(fields=["formulir", "urut"], name="baris_urut_unik"),
            models.CheckConstraint(condition=Q(urut__gte=1) & Q(urut__lte=MAKS_BARIS),
                                   name="baris_urut_1_sampai_12"),
        ]

    def __str__(self):
        return f"{self.formulir} #{self.urut}"

    @property
    def lengkap(self):
        return None not in (self.jam_mulai, self.jam_selesai, self.actual)
