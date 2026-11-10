from django.urls import path

from . import views

urlpatterns = [
    path("", views.beranda, name="beranda"),
    # Operator
    path("operator/", views.operator_beranda, name="operator_beranda"),
    path("operator/nama/", views.operator_pilih_nama, name="operator_pilih_nama"),
    path("operator/formulir/<int:pk>/", views.operator_isi, name="operator_isi"),
    # Admin
    path("panel/", views.panel_beranda, name="panel_beranda"),
    path("panel/plan/<int:mesin_id>/", views.panel_plan, name="panel_plan"),
    path("panel/salin/", views.panel_salin, name="panel_salin"),
    path("panel/setujui-semua/", views.panel_setujui_semua, name="panel_setujui_semua"),
    path("panel/formulir/<int:pk>/", views.panel_periksa, name="panel_periksa"),
    path("panel/formulir/<int:pk>/aksi/", views.panel_aksi, name="panel_aksi"),
    path("panel/ekspor/", views.panel_ekspor, name="panel_ekspor"),
]
