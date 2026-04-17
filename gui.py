"""
gui.py — Interface graphique pour scriptimage.py et decoupeimage.py
Dépendances : tkinter (stdlib), pdf2image, Pillow, numpy
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import sys
import io
from pathlib import Path


# ─────────────────────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────────────────────

def browse_file(var, filetypes=(("PDF", "*.pdf"),)):
    path = filedialog.askopenfilename(filetypes=filetypes)
    if path:
        var.set(path)


def browse_dir(var):
    path = filedialog.askdirectory()
    if path:
        var.set(path)


class RedirectText:
    """Redirige stdout/stderr vers un widget ScrolledText."""
    def __init__(self, widget: scrolledtext.ScrolledText):
        self.widget = widget

    def write(self, text):
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)
        self.widget.configure(state="disabled")

    def flush(self):
        pass


def run_in_thread(btn, log_widget, fn, *args, **kwargs):
    """Lance fn dans un thread, désactive le bouton pendant l'exécution."""
    log_widget.configure(state="normal")
    log_widget.delete("1.0", tk.END)
    log_widget.configure(state="disabled")

    redirect = RedirectText(log_widget)

    def task():
        btn.configure(state="disabled", text="En cours…")
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = redirect
        try:
            fn(*args, **kwargs)
        except Exception as e:
            redirect.write(f"\n[ERREUR] {e}\n")
        finally:
            sys.stdout, sys.stderr = old_out, old_err
            btn.configure(state="normal", text="▶  Lancer")

    threading.Thread(target=task, daemon=True).start()


# ─────────────────────────────────────────────────────────────
#  Onglet 1 : Extraction de colonne (scriptimage.py)
# ─────────────────────────────────────────────────────────────

def build_tab_extract(nb: ttk.Notebook):
    frame = ttk.Frame(nb, padding=12)
    nb.add(frame, text="1 · Extraire colonne PDF")

    # ── Variables ──────────────────────────────────────────
    v_pdf      = tk.StringVar(value="mon_livre.pdf")
    v_out      = tk.StringVar(value="colonnes_droites")
    v_excl     = tk.StringVar(value="1,2,3,900")
    v_col_s    = tk.DoubleVar(value=2/3)
    v_col_e    = tk.DoubleVar(value=1.0)
    v_dpi      = tk.IntVar(value=300)
    v_quality  = tk.IntVar(value=85)
    v_ml       = tk.IntVar(value=10)
    v_mr       = tk.IntVar(value=10)
    v_mt       = tk.IntVar(value=20)
    v_mb       = tk.IntVar(value=20)

    # ── Layout helpers ─────────────────────────────────────
    r = 0
    def lbl(text, row, col=0):
        ttk.Label(frame, text=text).grid(row=row, column=col, sticky="w", pady=2)

    def entry(var, row, col=1, width=30):
        ttk.Entry(frame, textvariable=var, width=width).grid(
            row=row, column=col, sticky="ew", pady=2, padx=(4, 0))

    frame.columnconfigure(1, weight=1)

    # ── Fichiers ───────────────────────────────────────────
    lbl("PDF source :", r)
    entry(v_pdf, r)
    ttk.Button(frame, text="…", width=3,
               command=lambda: browse_file(v_pdf)).grid(row=r, column=2, padx=4)
    r += 1

    lbl("Dossier de sortie :", r)
    entry(v_out, r)
    ttk.Button(frame, text="…", width=3,
               command=lambda: browse_dir(v_out)).grid(row=r, column=2, padx=4)
    r += 1

    lbl("Pages à exclure (virgules) :", r)
    entry(v_excl, r)
    r += 1

    # ── Colonne ────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1

    lbl("Début colonne (0–1) :", r);  entry(v_col_s, r, width=10); r += 1
    lbl("Fin colonne (0–1) :",   r);  entry(v_col_e, r, width=10); r += 1

    # ── Marges ─────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1

    for label, var in [("Marge gauche (px) :", v_ml), ("Marge droite (px) :", v_mr),
                       ("Marge haut (px) :",   v_mt), ("Marge bas (px) :",    v_mb)]:
        lbl(label, r); entry(var, r, width=10); r += 1

    # ── DPI / Qualité ──────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1

    lbl("DPI :", r);             entry(v_dpi,     r, width=10); r += 1
    lbl("Qualité JPEG (1-95) :", r); entry(v_quality, r, width=10); r += 1

    # ── Bouton ─────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1

    log = scrolledtext.ScrolledText(frame, height=8, state="disabled",
                                    font=("Courier", 10))
    log.grid(row=r+1, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
    frame.rowconfigure(r+1, weight=1)

    btn = ttk.Button(frame, text="▶  Lancer")
    btn.grid(row=r, column=0, columnspan=3, pady=4)

    def lancer():
        try:
            excl = {int(x.strip()) for x in v_excl.get().split(",") if x.strip()}
        except ValueError:
            messagebox.showerror("Erreur", "Pages à exclure : entiers séparés par des virgules.")
            return

        from scriptimage import extraire_colonnes
        run_in_thread(
            btn, log, extraire_colonnes,
            pdf_path      = v_pdf.get(),
            output_dir    = v_out.get(),
            pages_exclues = excl,
            col_start     = v_col_s.get(),
            col_end       = v_col_e.get(),
            dpi           = v_dpi.get(),
            jpeg_quality  = v_quality.get(),
            margin_left   = v_ml.get(),
            margin_right  = v_mr.get(),
            margin_top    = v_mt.get(),
            margin_bottom = v_mb.get(),
        )

    btn.configure(command=lancer)
    return frame


# ─────────────────────────────────────────────────────────────
#  Onglet 2 : Découpe blocs/lignes (decoupeimage.py)
# ─────────────────────────────────────────────────────────────

def build_tab_decoupe(nb: ttk.Notebook):
    frame = ttk.Frame(nb, padding=12)
    nb.add(frame, text="2 · Découper blocs / lignes")

    # ── Variables ──────────────────────────────────────────
    v_inp     = tk.StringVar(value="colonnes_droites")
    v_out     = tk.StringVar(value="decoupes")

    v_b_encre = tk.DoubleVar(value=0.005)
    v_b_gap   = tk.IntVar(value=8)
    v_b_hmin  = tk.IntVar(value=40)

    v_l_encre = tk.DoubleVar(value=0.003)
    v_l_gap   = tk.IntVar(value=3)
    v_l_hmin  = tk.IntVar(value=15)

    v_marge   = tk.IntVar(value=4)
    v_binseuil= tk.IntVar(value=200)
    v_quality = tk.IntVar(value=85)

    # ── Layout ─────────────────────────────────────────────
    r = 0
    frame.columnconfigure(1, weight=1)

    def lbl(text, row, col=0):
        ttk.Label(frame, text=text).grid(row=row, column=col, sticky="w", pady=2)

    def entry(var, row, col=1, width=14):
        ttk.Entry(frame, textvariable=var, width=width).grid(
            row=row, column=col, sticky="w", pady=2, padx=(4, 0))

    lbl("Dossier source :", r)
    ttk.Entry(frame, textvariable=v_inp, width=30).grid(
        row=r, column=1, sticky="ew", pady=2, padx=(4, 0))
    ttk.Button(frame, text="…", width=3,
               command=lambda: browse_dir(v_inp)).grid(row=r, column=2, padx=4)
    r += 1

    lbl("Dossier de sortie :", r)
    ttk.Entry(frame, textvariable=v_out, width=30).grid(
        row=r, column=1, sticky="ew", pady=2, padx=(4, 0))
    ttk.Button(frame, text="…", width=3,
               command=lambda: browse_dir(v_out)).grid(row=r, column=2, padx=4)
    r += 1

    # ── Blocs ──────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1
    ttk.Label(frame, text="— Détection des blocs —", foreground="gray").grid(
        row=r, column=0, columnspan=3, sticky="w"); r += 1

    lbl("Seuil encre (0–1) :", r);        entry(v_b_encre, r); r += 1
    lbl("Gap min entre blocs (px) :", r); entry(v_b_gap,   r); r += 1
    lbl("Hauteur min bloc (px) :", r);    entry(v_b_hmin,  r); r += 1

    # ── Lignes ─────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1
    ttk.Label(frame, text="— Détection des lignes —", foreground="gray").grid(
        row=r, column=0, columnspan=3, sticky="w"); r += 1

    lbl("Seuil encre (0–1) :", r);         entry(v_l_encre, r); r += 1
    lbl("Gap min entre lignes (px) :", r); entry(v_l_gap,   r); r += 1
    lbl("Hauteur min ligne (px) :", r);    entry(v_l_hmin,  r); r += 1

    # ── Divers ─────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1

    lbl("Marge verticale (px) :", r);     entry(v_marge,    r); r += 1
    lbl("Seuil binarisation (0-255) :", r); entry(v_binseuil, r); r += 1
    lbl("Qualité JPEG (1-95) :", r);      entry(v_quality,  r); r += 1

    # ── Bouton ─────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6)
    r += 1

    log = scrolledtext.ScrolledText(frame, height=8, state="disabled",
                                    font=("Courier", 10))
    log.grid(row=r+1, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
    frame.rowconfigure(r+1, weight=1)

    btn = ttk.Button(frame, text="▶  Lancer")
    btn.grid(row=r, column=0, columnspan=3, pady=4)

    def lancer():
        import decoupeimage as di

        # Écrase temporairement les constantes globales du module
        di.INPUT_DIR          = v_inp.get()
        di.OUTPUT_DIR         = v_out.get()
        di.BLOC_SEUIL_ENCRE   = v_b_encre.get()
        di.BLOC_MIN_GAP       = v_b_gap.get()
        di.BLOC_HAUTEUR_MIN   = v_b_hmin.get()
        di.LIGNE_SEUIL_ENCRE  = v_l_encre.get()
        di.LIGNE_MIN_GAP      = v_l_gap.get()
        di.LIGNE_HAUTEUR_MIN  = v_l_hmin.get()
        di.MARGE_V            = v_marge.get()
        di.BINARISATION_SEUIL = v_binseuil.get()
        di.JPEG_QUALITY       = v_quality.get()

        run_in_thread(btn, log, di.main)

    btn.configure(command=lancer)
    return frame


# ─────────────────────────────────────────────────────────────
#  Fenêtre principale
# ─────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("DicoImage — Pipeline PDF → Découpes")
    root.minsize(520, 600)
    root.resizable(True, True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    build_tab_extract(nb)
    build_tab_decoupe(nb)

    root.mainloop()


if __name__ == "__main__":
    main()
