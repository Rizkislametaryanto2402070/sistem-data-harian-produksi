from django.contrib import admin

from .models import BarisProduksi, Formulir, Item, Mesin, Operator


@admin.register(Mesin)
class MesinAdmin(admin.ModelAdmin):
    list_display = ("kode", "urutan", "aktif")
    list_editable = ("aktif",)
    # Kode mesin dipakai untuk memetakan ke template Excel, jadi tidak boleh diubah/dihapus.
    readonly_fields = ("kode", "urutan")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("nama", "no_part", "aktif")
    list_editable = ("aktif",)
    list_filter = ("aktif",)
    search_fields = ("nama", "no_part")


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ("nama", "aktif")
    list_editable = ("aktif",)
    list_filter = ("aktif",)
    search_fields = ("nama",)


class BarisInline(admin.TabularInline):
    model = BarisProduksi
    extra = 0
    max_num = 12


@admin.register(Formulir)
class FormulirAdmin(admin.ModelAdmin):
    list_display = ("tanggal", "shift", "mesin", "pengisi", "operator", "status")
    list_filter = ("tanggal", "shift", "mesin")
    inlines = [BarisInline]
