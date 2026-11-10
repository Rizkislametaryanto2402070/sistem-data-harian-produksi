from django import forms
from django.forms import inlineformset_factory, modelformset_factory

from .models import MAKS_BARIS, BarisProduksi, Formulir, Item, Shift


class PilihHariShiftForm(forms.Form):
    tanggal = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    shift = forms.ChoiceField(choices=Shift.choices)


# ---- Admin: pilih item + isi plan ----------------------------------------------------------

class BarisPlanForm(forms.ModelForm):
    class Meta:
        model = BarisProduksi
        fields = ("item", "plan")
        widgets = {"plan": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hanya item aktif sebagai pilihan; item lama yang sudah dipakai tetap tampil.
        qs = Item.objects.filter(aktif=True)
        if self.instance.pk:
            qs = Item.objects.filter(pk=self.instance.item_id) | qs
        self.fields["item"].queryset = qs.distinct()
        self.fields["item"].label_from_instance = lambda i: i.label


BarisPlanFormSet = inlineformset_factory(
    Formulir, BarisProduksi, form=BarisPlanForm,
    extra=MAKS_BARIS, max_num=MAKS_BARIS, validate_max=True, can_delete=True,   # total form dibatasi max_num
)


# ---- Operator: jam, actual, NG, keterangan -------------------------------------------------

class BarisOperatorForm(forms.ModelForm):
    class Meta:
        model = BarisProduksi
        fields = ("jam_mulai", "jam_selesai", "actual", "ng", "keterangan")
        widgets = {
            "jam_mulai": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "jam_selesai": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "actual": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "ng": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "keterangan": forms.TextInput(attrs={"maxlength": 120}),
        }

    def clean(self):
        data = super().clean()
        actual, ng = data.get("actual"), data.get("ng")
        if actual is not None and ng is not None and ng > actual:
            self.add_error("ng", "NG tidak boleh lebih besar dari Actual.")
        return data


BarisOperatorFormSet = modelformset_factory(BarisProduksi, form=BarisOperatorForm, extra=0)
