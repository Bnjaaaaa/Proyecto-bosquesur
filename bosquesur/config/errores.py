from django.shortcuts import render


def prohibido(request, exception=None):
    return render(request, "errores/403.html", status=403)


def no_encontrado(request, exception=None):
    return render(request, "errores/404.html", status=404)
