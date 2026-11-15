@echo off
chcp 65001 >nul
if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
)
python manage.py test
python manage.py verificar_auditoria
pause
