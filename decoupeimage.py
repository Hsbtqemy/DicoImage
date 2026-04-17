"""
slice_columns.py
================
Découpe automatique des JPEG de colonnes en bandes horizontales,
à deux niveaux : blocs/paragraphes ET lignes de texte individuelles.

Méthode : projection horizontale (horizontal profile projection).
On somme les pixels sombres sur chaque ligne horizontale de l'image.
Les creux (zones presque blanches) indiquent les espaces entre blocs ou lignes.

Dépendances :
    pip install Pillow numpy
"""

import numpy as np
from PIL import Image
from pathlib import Path


# ─────────────────────────────────────────────
#  CONFIGURATION  ←  modifie ces valeurs
# ─────────────────────────────────────────────

INPUT_DIR  = "colonnes_droites"   # dossier contenant les JPEG du script précédent
OUTPUT_DIR = "decoupes"           # dossier de sortie racine

# --- Détection des BLOCS (paragraphes) ---
# Seuil d'encre : une ligne horizontale est considérée "vide" si le pourcentage
# de pixels sombres est inférieur à ce seuil (0.0–1.0).
BLOC_SEUIL_ENCRE    = 0.005   # 0.5 % de pixels sombres → ligne blanche
# Nombre minimum de lignes blanches consécutives pour constituer une séparation de bloc.
BLOC_MIN_GAP        = 8       # pixels (à 300 dpi ≈ 0.7 mm)
# Hauteur minimale d'un bloc pour être conservé (évite les artefacts).
BLOC_HAUTEUR_MIN    = 40      # pixels

# --- Détection des LIGNES dans chaque bloc ---
# Même logique mais paramètres plus fins.
LIGNE_SEUIL_ENCRE   = 0.003   # plus sensible
LIGNE_MIN_GAP       = 3       # inter-ligne plus petit
LIGNE_HAUTEUR_MIN   = 15      # hauteur minimale d'une ligne de texte

# Marge verticale ajoutée autour de chaque découpe (pour ne pas couper trop ras).
MARGE_V = 4   # pixels

# Seuil de binarisation (0–255) : en dessous = pixel sombre (encre).
BINARISATION_SEUIL = 200

# Qualité JPEG de sortie.
JPEG_QUALITY = 85


# ─────────────────────────────────────────────
#  FONCTIONS UTILITAIRES
# ─────────────────────────────────────────────

def binariser(img: Image.Image, seuil: int = 200) -> np.ndarray:
    """Convertit en niveaux de gris et binarise. Retourne un tableau bool (True = sombre)."""
    gray = img.convert("L")
    arr  = np.array(gray)
    return arr < seuil   # True là où il y a de l'encre


def profil_projection(binaire: np.ndarray) -> np.ndarray:
    """Somme horizontale : pour chaque ligne, proportion de pixels sombres."""
    return binaire.sum(axis=1) / binaire.shape[1]


def detecter_segments(
    profil: np.ndarray,
    seuil_encre: float,
    min_gap: int,
    hauteur_min: int,
) -> list[tuple[int, int]]:
    """
    Retourne une liste de (debut, fin) en pixels pour chaque segment de texte détecté.
    Un segment = zone contiguë dont le profil dépasse seuil_encre,
    séparée des voisins par au moins min_gap lignes vides.
    """
    n = len(profil)
    a_encre = profil >= seuil_encre   # booléen par ligne

    # Dilatation : comble les gaps < min_gap pour éviter de couper au milieu d'un mot
    dilatee = a_encre.copy()
    for i in range(n):
        if a_encre[i]:
            start = max(0, i - min_gap)
            end   = min(n, i + min_gap + 1)
            dilatee[start:end] = True

    segments = []
    en_segment = False
    debut = 0

    for i in range(n):
        if dilatee[i] and not en_segment:
            debut = i
            en_segment = True
        elif not dilatee[i] and en_segment:
            fin = i
            if fin - debut >= hauteur_min:
                segments.append((debut, fin))
            en_segment = False

    if en_segment and (n - debut) >= hauteur_min:
        segments.append((debut, n))

    return segments


def ajouter_marge(debut: int, fin: int, hauteur_image: int, marge: int) -> tuple[int, int]:
    return max(0, debut - marge), min(hauteur_image, fin + marge)


def sauvegarder(img: Image.Image, path: Path, quality: int = 85):
    out = img.convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path, "JPEG", quality=quality)


# ─────────────────────────────────────────────
#  TRAITEMENT PRINCIPAL
# ─────────────────────────────────────────────

def traiter_image(img_path: Path, output_base: Path):
    img = Image.open(img_path)
    w, h = img.size
    binaire = binariser(img, BINARISATION_SEUIL)
    profil  = profil_projection(binaire)

    # ── Niveau 1 : Blocs ──────────────────────────────────────────
    blocs = detecter_segments(profil, BLOC_SEUIL_ENCRE, BLOC_MIN_GAP, BLOC_HAUTEUR_MIN)

    dossier_blocs  = output_base / "blocs"
    dossier_lignes = output_base / "lignes"

    for i_bloc, (b_debut, b_fin) in enumerate(blocs):
        d, f = ajouter_marge(b_debut, b_fin, h, MARGE_V)
        bloc_img = img.crop((0, d, w, f))

        # Sauvegarde du bloc
        nom_bloc = f"bloc_{i_bloc+1:03d}.jpg"
        sauvegarder(bloc_img, dossier_blocs / nom_bloc, JPEG_QUALITY)

        # ── Niveau 2 : Lignes dans ce bloc ────────────────────────
        bloc_bin    = binariser(bloc_img, BINARISATION_SEUIL)
        bloc_profil = profil_projection(bloc_bin)
        lignes = detecter_segments(
            bloc_profil, LIGNE_SEUIL_ENCRE, LIGNE_MIN_GAP, LIGNE_HAUTEUR_MIN
        )

        bh = bloc_img.size[1]
        for i_ligne, (l_debut, l_fin) in enumerate(lignes):
            ld, lf = ajouter_marge(l_debut, l_fin, bh, MARGE_V)
            ligne_img = bloc_img.crop((0, ld, w, lf))
            nom_ligne = f"bloc_{i_bloc+1:03d}_ligne_{i_ligne+1:03d}.jpg"
            sauvegarder(ligne_img, dossier_lignes / nom_ligne, JPEG_QUALITY)

    return len(blocs)


def main():
    input_dir  = Path(INPUT_DIR)
    output_dir = Path(OUTPUT_DIR)

    images = sorted(input_dir.glob("*.jpg")) + sorted(input_dir.glob("*.jpeg"))
    if not images:
        print(f"Aucun JPEG trouvé dans : {input_dir.resolve()}")
        return

    print(f"{len(images)} image(s) à traiter → {output_dir.resolve()}")
    print()

    total_blocs = 0
    for img_path in images:
        # Dossier de sortie calqué sur le nom du fichier source
        page_dir = output_dir / img_path.stem
        n_blocs  = traiter_image(img_path, page_dir)
        total_blocs += n_blocs
        print(f"  {img_path.name}  →  {n_blocs} bloc(s) détecté(s)")

    print()
    print(f"Terminé. {total_blocs} blocs au total sur {len(images)} pages.")
    print(f"Structure de sortie :")
    print(f"  {OUTPUT_DIR}/")
    print(f"  ├── page_0001/")
    print(f"  │   ├── blocs/     (un JPEG par bloc/paragraphe)")
    print(f"  │   └── lignes/    (un JPEG par ligne de texte)")
    print(f"  ├── page_0002/")
    print(f"  │   └── ...")


if __name__ == "__main__":
    main()
