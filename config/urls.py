from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Kelola Data Produksi"
admin.site.site_title = "Kelola Data Produksi"
admin.site.index_title = "Master data"

urlpatterns = [
    path("kelola/", admin.site.urls),
    path("akun/", include("django.contrib.auth.urls")),
    path("", include("produksi.urls")),
]
