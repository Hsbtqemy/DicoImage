"""
extract_right_column.py
=======================
Extrait la colonne de droite de chaque page d'un PDF scanné (3 colonnes)
et sauvegarde le résultat en JPEG.

Dépendances :
    pip install pdf2image Pillow
    + Poppler installé sur le système :
        Linux  : sudo apt install poppler-utils
        macOS  : brew install poppler
        Windows: https://github.com/oschwartz10612/poppler-windows/releases
"""

from pdf2image import convert_from_path
from PIL import Image
from pathlib import Path

# ─────────────────────────────────────────────
#  CONFIGURATION  ←  modifie ces valeurs
# ─────────────────────────────────────────────

PDF_PATH = "mon_livre.pdf"          # chemin vers ton PDF

OUTPUT_DIR = "colonnes_droites"     # dossier de sortie (créé automatiquement)

# Pages à EXCLURE (numérotation PDF, commence à 1).
# Ex : couverture, dos, planches hors-colonne, index…
PAGES_A_EXCLURE = {
    1, 2, 3,        # couverture / pages liminaires
    900,            # dernière page
    # ajoute autant de numéros que nécessaire
}

# Position de la colonne droite (fractions de la largeur de la page).
# Par défaut : tiers droit → de 2/3 à la fin.
# Ajuste COL_START si les colonnes ne sont pas exactement égales.
COL_START = 2 / 3   # début de la colonne droite (0.0 → 1.0)
COL_END   = 1.0     # fin (1.0 = bord droit)

# Marge intérieure à rogner de chaque côté de la colonne (en pixels à 300 dpi).
# Utile pour supprimer les filets de séparation ou débordements.
MARGIN_LEFT  = 10   # pixels à enlever à gauche de la colonne
MARGIN_RIGHT = 10   # pixels à enlever à droite de la colonne
MARGIN_TOP   = 20   # pixels à enlever en haut
MARGIN_BOTTOM= 20   # pixels à enlever en bas

# Résolution de rastérisation (dpi). 300 = bonne qualité, 200 = plus rapide/léger.
DPI = 300

# Qualité JPEG (1-95). 85 est un bon compromis qualité/poids.
JPEG_QUALITY = 85

# ─────────────────────────────────────────────
#  TRAITEMENT
# ─────────────────────────────────────────────

def extraire_colonnes(
    pdf_path: str,
    output_dir: str,
    pages_exclues: set,
    col_start: float = 2/3,
    col_end: float = 1.0,
    dpi: int = 300,
    jpeg_quality: int = 85,
    margin_left: int = 10,
    margin_right: int = 10,
    margin_top: int = 20,
    margin_bottom: int = 20,
):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Ouverture de : {pdf_path}")
    print(f"Résolution   : {dpi} dpi")
    print(f"Dossier de sortie : {out.resolve()}")
    print()

    # Conversion par lots pour limiter la RAM (1 page à la fois)
    from pdf2image import pdfinfo_from_path
    info = pdfinfo_from_path(pdf_path)
    total_pages = info["Pages"]
    print(f"Nombre total de pages dans le PDF : {total_pages}")

    saved = 0
    skipped = 0

    for page_num in range(1, total_pages + 1):
        if page_num in pages_exclues:
            print(f"  [IGNORÉ]  page {page_num:04d}")
            skipped += 1
            continue

        # Rastérisation d'une seule page à la fois (économise la RAM)
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page_num,
            last_page=page_num,
        )
        img: Image.Image = images[0]
        w, h = img.size

        # Calcul de la boîte de découpe
        left   = int(w * col_start) + margin_left
        right  = int(w * col_end)   - margin_right
        top    = margin_top
        bottom = h - margin_bottom

        # Sécurité : évite les coordonnées invalides
        left   = max(0, left)
        right  = min(w, right)
        top    = max(0, top)
        bottom = min(h, bottom)

        colonne = img.crop((left, top, right, bottom))

        # Conversion RGB si nécessaire (JPEG ne supporte pas RGBA)
        if colonne.mode != "RGB":
            colonne = colonne.convert("RGB")

        out_path = out / f"page_{page_num:04d}.jpg"
        colonne.save(out_path, "JPEG", quality=jpeg_quality)

        print(f"  [OK]      page {page_num:04d}  →  {out_path.name}")
        saved += 1

    print()
    print(f"Terminé. {saved} images sauvegardées, {skipped} pages ignorées.")
    print(f"Dossier : {out.resolve()}")


if __name__ == "__main__":
    extraire_colonnes(
        pdf_path      = PDF_PATH,
        output_dir    = OUTPUT_DIR,
        pages_exclues = PAGES_A_EXCLURE,
        col_start     = COL_START,
        col_end       = COL_END,
        dpi           = DPI,
        jpeg_quality  = JPEG_QUALITY,
        margin_left   = MARGIN_LEFT,
        margin_right  = MARGIN_RIGHT,
        margin_top    = MARGIN_TOP,
        margin_bottom = MARGIN_BOTTOM,
    )