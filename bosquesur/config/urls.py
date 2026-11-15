from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from cuentas.views import inicio

admin.site.site_header = "BosqueSur Maderas SpA · Administración"
admin.site.site_title = "BosqueSur Admin"
admin.site.index_title = "Datos maestros y usuarios"

urlpatterns = [
    path("", inicio, name="inicio"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="cuentas/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("operaciones.urls")),
    path("auditoria/", include("auditoria.urls")),
    path("api/", include("api.urls")),
    path("admin/", admin.site.urls),
]

handler403 = "config.errores.prohibido"
handler404 = "config.errores.no_encontrado"
