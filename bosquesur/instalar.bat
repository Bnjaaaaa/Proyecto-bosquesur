@echo off
chcp 65001 >nul
title BosqueSur - Instalacion
echo.
echo  === BosqueSur Maderas SpA - Instalacion del prototipo ===
echo.
echo  Modo automatico: usa MySQL/MariaDB (XAMPP) si esta iniciado en el puerto 3306;
echo  si XAMPP no esta activo, usa SQLite local automaticamente para evitar fallos.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo  [ERROR] No se encontro Python. Instale Python 3.12+ desde python.org
  echo          y marque "Add python.exe to PATH" durante la instalacion.
  pause
  exit /b 1
)

if not exist venv (
  echo  [1/5] Creando entorno virtual...
  python -m venv venv >nul 2>nul
)
if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
  echo  [INFO] Entorno virtual activado.
) else (
  echo  [INFO] Continuando con Python del sistema.
)

echo  [2/5] Verificando e instalando dependencias...
pip install -r requirements.txt || goto error

echo  [3/5] Verificando motor de base de datos...
python manage.py crear_bd || goto error

echo  [4/5] Aplicando migraciones de base de datos...
python manage.py migrate || goto error

echo  [5/5] Cargando datos de demostracion (usuarios, predios, paquetes QR, compras, ventas)...
python manage.py cargar_demo || goto error

echo.
echo  Instalacion terminada. Ejecute iniciar.bat para abrir el sistema.
echo.
pause
exit /b 0

:error
echo.
echo  [ERROR] La instalacion se detuvo. Revise el mensaje de arriba.
pause
exit /b 1
