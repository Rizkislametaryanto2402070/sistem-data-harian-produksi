import csv

from django.core.management.base import BaseCommand, CommandError

from produksi.models import Item


class Command(BaseCommand):
    help = "Impor daftar item/part dari CSV berkolom: nama,no_part (baris pertama = judul kolom)."

    def add_arguments(self, parser):
        parser.add_argument("berkas", help="Path file CSV")

    def handle(self, *args, **opts):
        baru = ada = 0
        try:
            with open(opts["berkas"], newline="", encoding="utf-8-sig") as fh:
                pembaca = csv.DictReader(fh)
                if not pembaca.fieldnames or "nama" not in pembaca.fieldnames:
                    raise CommandError("CSV harus punya kolom 'nama' (dan 'no_part').")
                for baris in pembaca:
                    nama = (baris.get("nama") or "").strip()
                    if not nama:
                        continue
                    _, dibuat = Item.objects.get_or_create(
                        nama=nama, no_part=(baris.get("no_part") or "").strip())
                    baru += dibuat
                    ada += not dibuat
        except FileNotFoundError:
            raise CommandError(f"File tidak ditemukan: {opts['berkas']}")
        self.stdout.write(self.style.SUCCESS(f"Selesai: {baru} item baru, {ada} sudah ada."))
