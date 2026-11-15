@echo off
chcp 65001 >nul
title BosqueSur - Servidor
if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
)

echo.
echo  === BosqueSur Maderas SpA · Sistema Integrado ===
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.conf import settings; print('  Motor BD activo:', settings.DB_MOTOR_ACTIVO)"
echo  Abra en este PC:        http://127.0.0.1:8000
echo  App Movil (JWT):        http://127.0.0.1:8000/app-movil/
echo  Desde un celular en la misma red Wi-Fi: http://IP-DE-ESTE-PC:8000  (ver ipconfig)
echo  Usuarios demo: gerente, administrativo, faena, patio, admin  -  Clave: Bosque2026!
echo  Para detener el servidor presione Ctrl+C
echo.
start "" http://127.0.0.1:8000
python manage.py runserver 0.0.0.0:8000
