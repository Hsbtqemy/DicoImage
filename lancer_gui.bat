@echo off
cd /d "%~dp0"

:: ── Vérification de Python ─────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python introuvable. Installe-le depuis https://www.python.org
    pause
    exit /b 1
)

:: ── Création du venv si absent ────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Création de l'environnement virtuel...
    python -m venv .venv
)

:: ── Activation du venv ────────────────────────────────────
call .venv\Scripts\activate.bat

:: ── Installation des dépendances si absentes ──────────────
python -c "import pdf2image" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installation de pdf2image...
    pip install pdf2image
)

python -c "import PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installation de Pillow...
    pip install Pillow
)

python -c "import numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installation de numpy...
    pip install numpy
)

:: ── Lancement de l'interface ──────────────────────────────
echo [INFO] Lancement de l'interface...
python gui.py

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Le script s'est termine avec une erreur.
    pause
)
