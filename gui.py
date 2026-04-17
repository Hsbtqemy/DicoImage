"""
gui.py — Interface graphique pour scriptimage.py et decoupeimage.py
Dépendances : tkinter (stdlib), pdf2image, Pillow, numpy
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import sys
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw


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
#  Prévisualisation (utilisée par l'onglet Calibrer)
# ─────────────────────────────────────────────────────────────

def make_preview(img: Image.Image, col_s, col_e, ml, mr, mt, mb) -> Image.Image:
    w, h = img.size
    left   = max(0, int(w * col_s) + ml)
    right  = min(w, int(w * col_e) - mr)
    top    = max(0, mt)
    bottom = min(h, h - mb)

    rgba = img.convert("RGBA")
    dark = Image.new("RGBA", rgba.size, (0, 0, 0, 150))
    preview = Image.alpha_composite(rgba, dark)

    if right > left and bottom > top:
        bright = rgba.crop((left, top, right, bottom))
        preview.paste(bright, (left, top))
        draw = ImageDraw.Draw(preview)
        draw.rectangle([left, top, right - 1, bottom - 1],
                       outline=(220, 60, 60, 255), width=2)

    return preview.convert("RGB")


def fit_to(img: Image.Image, max_w: int, max_h: int):
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS), scale


# ─────────────────────────────────────────────────────────────
#  Onglet 1 : Extraction de colonne (scriptimage.py)
# ─────────────────────────────────────────────────────────────

def build_tab_extract(nb: ttk.Notebook, sv: dict):
    frame = ttk.Frame(nb, padding=12)
    nb.add(frame, text="1 · Extraire colonne PDF")
    frame.columnconfigure(1, weight=1)

    r = 0

    def lbl(text, row, col=0):
        ttk.Label(frame, text=text).grid(row=row, column=col, sticky="w", pady=2)

    def entry(var, row, col=1, width=30):
        ttk.Entry(frame, textvariable=var, width=width).grid(
            row=row, column=col, sticky="ew", pady=2, padx=(4, 0))

    lbl("PDF source :", r)
    entry(sv["pdf"], r)
    ttk.Button(frame, text="…", width=3,
               command=lambda: browse_file(sv["pdf"])).grid(row=r, column=2, padx=4)
    r += 1

    lbl("Dossier de sortie :", r)
    entry(sv["out_col"], r)
    ttk.Button(frame, text="…", width=3,
               command=lambda: browse_dir(sv["out_col"])).grid(row=r, column=2, padx=4)
    r += 1

    lbl("Pages à exclure (virgules) :", r)
    entry(sv["excl"], r)
    r += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1

    lbl("Début colonne (0–1) :", r); entry(sv["col_s"], r, width=10); r += 1
    lbl("Fin colonne (0–1) :",   r); entry(sv["col_e"], r, width=10); r += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1

    for label, key in [("Marge gauche (px) :", "ml"), ("Marge droite (px) :", "mr"),
                       ("Marge haut (px) :",   "mt"), ("Marge bas (px) :",    "mb")]:
        lbl(label, r); entry(sv[key], r, width=10); r += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1

    lbl("DPI :", r);                 entry(sv["dpi"],     r, width=10); r += 1
    lbl("Qualité JPEG (1-95) :", r); entry(sv["quality"], r, width=10); r += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1

    log = scrolledtext.ScrolledText(frame, height=8, state="disabled",
                                    font=("Courier", 10))
    log.grid(row=r + 1, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
    frame.rowconfigure(r + 1, weight=1)

    btn = ttk.Button(frame, text="▶  Lancer")
    btn.grid(row=r, column=0, columnspan=3, pady=4)

    def lancer():
        try:
            excl = set()
            for part in sv["excl"].get().split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-", 1)
                    excl.update(range(int(a.strip()), int(b.strip()) + 1))
                elif part:
                    excl.add(int(part))
        except ValueError:
            messagebox.showerror("Erreur", "Pages à exclure : entiers séparés par des virgules.")
            return
        from scriptimage import extraire_colonnes
        run_in_thread(
            btn, log, extraire_colonnes,
            pdf_path      = sv["pdf"].get(),
            output_dir    = sv["out_col"].get(),
            pages_exclues = excl,
            col_start     = sv["col_s"].get(),
            col_end       = sv["col_e"].get(),
            dpi           = sv["dpi"].get(),
            jpeg_quality  = sv["quality"].get(),
            margin_left   = sv["ml"].get(),
            margin_right  = sv["mr"].get(),
            margin_top    = sv["mt"].get(),
            margin_bottom = sv["mb"].get(),
        )

    btn.configure(command=lancer)


# ─────────────────────────────────────────────────────────────
#  Onglet 2 : Calibrage visuel
# ─────────────────────────────────────────────────────────────

CANVAS_W, CANVAS_H = 380, 540


def build_tab_calibrer(nb: ttk.Notebook, sv: dict):
    frame = ttk.Frame(nb, padding=12)
    nb.add(frame, text="2 · Calibrer")
    frame.columnconfigure(0, weight=3)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(1, weight=1)

    # ── Barre du haut ──────────────────────────────────────
    top = ttk.Frame(frame)
    top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    top.columnconfigure(1, weight=1)

    ttk.Label(top, text="Page n° :").grid(row=0, column=0, sticky="w")
    v_page = tk.IntVar(value=4)
    ttk.Spinbox(top, from_=1, to=9999, textvariable=v_page, width=6).grid(
        row=0, column=1, sticky="w", padx=6)

    btn_load = ttk.Button(top, text="Charger la page")
    btn_load.grid(row=0, column=2, padx=(8, 0))

    lbl_info = ttk.Label(top, text="← choisir une page et charger", foreground="gray")
    lbl_info.grid(row=0, column=3, padx=(12, 0))

    # ── Canvas ─────────────────────────────────────────────
    canvas = tk.Canvas(frame, width=CANVAS_W, height=CANVAS_H,
                       bg="#1e1e1e", relief="sunken", bd=1)
    canvas.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

    # ── Panneau de sliders ─────────────────────────────────
    ctrl = ttk.Frame(frame)
    ctrl.grid(row=1, column=1, sticky="new")
    ctrl.columnconfigure(1, weight=1)

    state = {"img": None, "tk_ref": None}

    def refresh(*_):
        img = state["img"]
        if img is None:
            return
        preview = make_preview(
            img,
            sv["col_s"].get(), sv["col_e"].get(),
            sv["ml"].get(), sv["mr"].get(),
            sv["mt"].get(), sv["mb"].get(),
        )
        fitted, _ = fit_to(preview, CANVAS_W, CANVAS_H)
        tk_img = ImageTk.PhotoImage(fitted)
        state["tk_ref"] = tk_img
        canvas.delete("all")
        canvas.create_image(CANVAS_W // 2, CANVAS_H // 2, anchor="center", image=tk_img)

    def add_slider(label, var, row, from_, to, is_float=False):
        ttk.Label(ctrl, text=label).grid(row=row, column=0, sticky="w", pady=4)

        fmt = ".2f" if is_float else "d"
        val_lbl = ttk.Label(ctrl, text=f"{var.get():{fmt}}", width=6, anchor="e")
        val_lbl.grid(row=row, column=2, padx=(4, 0))

        def on_change(*_):
            if is_float:
                val_lbl.configure(text=f"{var.get():.2f}")
            else:
                var.set(int(var.get()))
                val_lbl.configure(text=f"{var.get():d}")
            refresh()

        ttk.Scale(ctrl, from_=from_, to=to, variable=var,
                  orient="horizontal", command=on_change).grid(
            row=row, column=1, sticky="ew", padx=4)

    r = 0
    ttk.Label(ctrl, text="— Colonne —", foreground="gray").grid(
        row=r, column=0, columnspan=3, sticky="w", pady=(0, 2)); r += 1
    add_slider("Début",  sv["col_s"], r, 0.0, 1.0, is_float=True); r += 1
    add_slider("Fin",    sv["col_e"], r, 0.0, 1.0, is_float=True); r += 1

    ttk.Separator(ctrl, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=8); r += 1
    ttk.Label(ctrl, text="— Marges (px) —", foreground="gray").grid(
        row=r, column=0, columnspan=3, sticky="w", pady=(0, 2)); r += 1
    add_slider("Gauche", sv["ml"], r, 0, 150); r += 1
    add_slider("Droite", sv["mr"], r, 0, 150); r += 1
    add_slider("Haut",   sv["mt"], r, 0, 150); r += 1
    add_slider("Bas",    sv["mb"], r, 0, 150); r += 1

    ttk.Label(ctrl, text="Les valeurs sont\nsynchronisées avec\nl'onglet 1.",
              foreground="gray", justify="left").grid(
        row=r + 1, column=0, columnspan=3, sticky="w", pady=(16, 0))

    # ── Chargement ─────────────────────────────────────────
    def charger():
        pdf = sv["pdf"].get()
        if not Path(pdf).exists():
            messagebox.showerror("Erreur", f"PDF introuvable :\n{pdf}")
            return

        btn_load.configure(state="disabled", text="Chargement…")
        lbl_info.configure(text="")

        def task():
            try:
                from pdf2image import convert_from_path
                page = v_page.get()
                images = convert_from_path(pdf, dpi=96, first_page=page, last_page=page)
                img = images[0]
                state["img"] = img
                frame.after(0, lambda: [
                    lbl_info.configure(text=f"page {page}  •  {img.size[0]}×{img.size[1]} px"),
                    refresh(),
                ])
            except Exception as e:
                frame.after(0, lambda: messagebox.showerror("Erreur", str(e)))
            finally:
                frame.after(0, lambda: btn_load.configure(state="normal", text="Charger la page"))

        threading.Thread(target=task, daemon=True).start()

    btn_load.configure(command=charger)


# ─────────────────────────────────────────────────────────────
#  Onglet 3 : Découpe blocs/lignes (decoupeimage.py)
# ─────────────────────────────────────────────────────────────

def build_tab_decoupe(nb: ttk.Notebook):
    frame = ttk.Frame(nb, padding=12)
    nb.add(frame, text="3 · Découper blocs / lignes")
    frame.columnconfigure(1, weight=1)

    v_inp      = tk.StringVar(value="colonnes_droites")
    v_out      = tk.StringVar(value="decoupes")
    v_b_encre  = tk.DoubleVar(value=0.005)
    v_b_gap    = tk.IntVar(value=8)
    v_b_hmin   = tk.IntVar(value=40)
    v_l_encre  = tk.DoubleVar(value=0.003)
    v_l_gap    = tk.IntVar(value=3)
    v_l_hmin   = tk.IntVar(value=15)
    v_marge    = tk.IntVar(value=4)
    v_binseuil = tk.IntVar(value=200)
    v_quality  = tk.IntVar(value=85)

    r = 0

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

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1
    ttk.Label(frame, text="— Détection des blocs —", foreground="gray").grid(
        row=r, column=0, columnspan=3, sticky="w"); r += 1

    lbl("Seuil encre (0–1) :", r);        entry(v_b_encre, r); r += 1
    lbl("Gap min entre blocs (px) :", r); entry(v_b_gap,   r); r += 1
    lbl("Hauteur min bloc (px) :", r);    entry(v_b_hmin,  r); r += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1
    ttk.Label(frame, text="— Détection des lignes —", foreground="gray").grid(
        row=r, column=0, columnspan=3, sticky="w"); r += 1

    lbl("Seuil encre (0–1) :", r);         entry(v_l_encre, r); r += 1
    lbl("Gap min entre lignes (px) :", r); entry(v_l_gap,   r); r += 1
    lbl("Hauteur min ligne (px) :", r);    entry(v_l_hmin,  r); r += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1

    lbl("Marge verticale (px) :", r);        entry(v_marge,    r); r += 1
    lbl("Seuil binarisation (0-255) :", r);  entry(v_binseuil, r); r += 1
    lbl("Qualité JPEG (1-95) :", r);         entry(v_quality,  r); r += 1

    ttk.Separator(frame, orient="horizontal").grid(
        row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1

    log = scrolledtext.ScrolledText(frame, height=8, state="disabled",
                                    font=("Courier", 10))
    log.grid(row=r + 1, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
    frame.rowconfigure(r + 1, weight=1)

    btn = ttk.Button(frame, text="▶  Lancer")
    btn.grid(row=r, column=0, columnspan=3, pady=4)

    def lancer():
        import decoupeimage as di
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


# ─────────────────────────────────────────────────────────────
#  Onglet 4 : Affinage des découpes
# ─────────────────────────────────────────────────────────────

CANVAS_W2, CANVAS_H2 = 400, 400


def make_crop_preview(img: Image.Image, t, b, l, r) -> Image.Image:
    w, h = img.size
    x0 = max(0, l)
    x1 = min(w, w - r)
    y0 = max(0, t)
    y1 = min(h, h - b)

    rgba = img.convert("RGBA")
    dark = Image.new("RGBA", rgba.size, (0, 0, 0, 150))
    preview = Image.alpha_composite(rgba, dark)

    if x1 > x0 and y1 > y0:
        bright = rgba.crop((x0, y0, x1, y1))
        preview.paste(bright, (x0, y0))
        draw = ImageDraw.Draw(preview)
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(60, 200, 100, 255), width=2)

    return preview.convert("RGB")


def build_tab_affinage(nb: ttk.Notebook):
    frame = ttk.Frame(nb, padding=12)
    nb.add(frame, text="4 · Affiner découpes")
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(1, weight=1)

    # ── Barre du haut ──────────────────────────────────────
    top = ttk.Frame(frame)
    top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    top.columnconfigure(1, weight=1)

    ttk.Label(top, text="Dossier :").grid(row=0, column=0, sticky="w")
    v_folder = tk.StringVar(value="decoupes")
    ttk.Entry(top, textvariable=v_folder, width=40).grid(
        row=0, column=1, sticky="ew", padx=6)
    ttk.Button(top, text="…", width=3,
               command=lambda: browse_dir(v_folder)).grid(row=0, column=2)
    btn_charger = ttk.Button(top, text="Charger")
    btn_charger.grid(row=0, column=3, padx=(8, 0))
    lbl_count = ttk.Label(top, text="", foreground="gray")
    lbl_count.grid(row=0, column=4, padx=(10, 0))

    # ── Panneau gauche : liste ─────────────────────────────
    left = ttk.Frame(frame)
    left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
    left.rowconfigure(0, weight=1)

    scrollbar = ttk.Scrollbar(left, orient="vertical")
    listbox = tk.Listbox(left, width=28, yscrollcommand=scrollbar.set,
                         selectmode="single", activestyle="dotbox")
    scrollbar.configure(command=listbox.yview)
    listbox.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    left.columnconfigure(0, weight=1)

    btn_del = ttk.Button(left, text="Supprimer", style="Danger.TButton")
    btn_del.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    # ── Panneau droit : canvas + sliders ──────────────────
    right = ttk.Frame(frame)
    right.grid(row=1, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(0, weight=1)

    canvas = tk.Canvas(right, width=CANVAS_W2, height=CANVAS_H2,
                       bg="#1e1e1e", relief="sunken", bd=1)
    canvas.grid(row=0, column=0, sticky="nsew")

    ctrl = ttk.Frame(right)
    ctrl.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    ctrl.columnconfigure(1, weight=1)
    ctrl.columnconfigure(3, weight=1)

    state = {"img": None, "path": None, "tk_ref": None, "paths": []}

    v_top = tk.IntVar(value=0)
    v_bot = tk.IntVar(value=0)
    v_lft = tk.IntVar(value=0)
    v_rgt = tk.IntVar(value=0)
    lbl_size = ttk.Label(right, text="", foreground="gray", anchor="center")
    lbl_size.grid(row=2, column=0, sticky="ew")

    def refresh_canvas(*_):
        img = state["img"]
        if img is None:
            return
        preview = make_crop_preview(img, v_top.get(), v_bot.get(),
                                    v_lft.get(), v_rgt.get())
        fitted, _ = fit_to(preview, CANVAS_W2, CANVAS_H2)
        tk_img = ImageTk.PhotoImage(fitted)
        state["tk_ref"] = tk_img
        canvas.delete("all")
        canvas.create_image(CANVAS_W2 // 2, CANVAS_H2 // 2,
                            anchor="center", image=tk_img)

    def make_slider(label, var, row, col_offset=0):
        c = col_offset
        ttk.Label(ctrl, text=label).grid(row=row, column=c, sticky="w", pady=3)
        val_lbl = ttk.Label(ctrl, text="0", width=4, anchor="e")
        val_lbl.grid(row=row, column=c + 2, padx=(2, 12))

        def on_change(*_):
            var.set(int(var.get()))
            val_lbl.configure(text=str(var.get()))
            refresh_canvas()

        ttk.Scale(ctrl, from_=0, to=200, variable=var,
                  orient="horizontal", command=on_change).grid(
            row=row, column=c + 1, sticky="ew", padx=4)

    make_slider("Haut",   v_top, 0, col_offset=0)
    make_slider("Bas",    v_bot, 1, col_offset=0)
    make_slider("Gauche", v_lft, 0, col_offset=4)
    make_slider("Droite", v_rgt, 1, col_offset=4)
    ctrl.columnconfigure(1, weight=1)
    ctrl.columnconfigure(5, weight=1)

    btn_save = ttk.Button(right, text="Sauvegarder le crop")
    btn_save.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    # ── Chargement d'un dossier ────────────────────────────
    def charger_dossier():
        folder = Path(v_folder.get())
        if not folder.exists():
            messagebox.showerror("Erreur", f"Dossier introuvable :\n{folder}")
            return
        paths = sorted(folder.rglob("*.jpg")) + sorted(folder.rglob("*.jpeg")) \
              + sorted(folder.rglob("*.JPG")) + sorted(folder.rglob("*.JPEG"))
        # dédoublonner en gardant l'ordre
        seen = set()
        paths = [p for p in paths if not (p in seen or seen.add(p))]
        state["paths"] = paths
        listbox.delete(0, tk.END)
        for p in paths:
            listbox.insert(tk.END, p.relative_to(folder))
        lbl_count.configure(text=f"{len(paths)} image(s)")
        if paths:
            listbox.selection_set(0)
            charger_image(0)

    btn_charger.configure(command=charger_dossier)

    # ── Chargement d'une image ─────────────────────────────
    def charger_image(idx):
        paths = state["paths"]
        if not paths or idx >= len(paths):
            return
        path = paths[idx]
        img = Image.open(path)
        state["img"] = img
        state["path"] = path
        w, h = img.size
        lbl_size.configure(text=f"{path.name}  •  {w}×{h} px")
        # réinitialiser les sliders et mettre à jour la plage max
        for var in (v_top, v_bot, v_lft, v_rgt):
            var.set(0)
        for slider in ctrl.winfo_children():
            if isinstance(slider, ttk.Scale):
                slider.configure(to=min(h // 2, 300) if slider in
                                 [ctrl.grid_slaves(row=0, column=1)[0] if ctrl.grid_slaves(row=0, column=1) else None,
                                  ctrl.grid_slaves(row=1, column=1)[0] if ctrl.grid_slaves(row=1, column=1) else None]
                                 else min(w // 2, 300))
        refresh_canvas()

    def on_select(event):
        sel = listbox.curselection()
        if sel:
            charger_image(sel[0])

    listbox.bind("<<ListboxSelect>>", on_select)

    def on_key(event):
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if event.keysym == "Down" and idx < listbox.size() - 1:
            listbox.selection_clear(idx)
            listbox.selection_set(idx + 1)
            listbox.see(idx + 1)
            charger_image(idx + 1)
        elif event.keysym == "Up" and idx > 0:
            listbox.selection_clear(idx)
            listbox.selection_set(idx - 1)
            listbox.see(idx - 1)
            charger_image(idx - 1)

    listbox.bind("<KeyPress>", on_key)

    # ── Sauvegarder ───────────────────────────────────────
    def sauvegarder():
        img = state["img"]
        path = state["path"]
        if img is None or path is None:
            return
        w, h = img.size
        box = (
            max(0, v_lft.get()),
            max(0, v_top.get()),
            min(w, w - v_rgt.get()),
            min(h, h - v_bot.get()),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            messagebox.showerror("Erreur", "Le crop est invalide (zone vide).")
            return
        cropped = img.crop(box).convert("RGB")
        cropped.save(path, "JPEG", quality=85)
        # Recharger pour refléter le nouveau contenu
        state["img"] = Image.open(path)
        v_top.set(0); v_bot.set(0); v_lft.set(0); v_rgt.set(0)
        refresh_canvas()
        lbl_size.configure(text=f"{path.name}  •  {cropped.size[0]}×{cropped.size[1]} px  ✓ sauvegardé")

    btn_save.configure(command=sauvegarder)

    # ── Supprimer ─────────────────────────────────────────
    def supprimer():
        path = state["path"]
        sel = listbox.curselection()
        if path is None or not sel:
            return
        if not messagebox.askyesno("Supprimer", f"Supprimer définitivement :\n{path.name} ?"):
            return
        idx = sel[0]
        path.unlink()
        state["paths"].pop(idx)
        listbox.delete(idx)
        state["img"] = None
        state["path"] = None
        canvas.delete("all")
        lbl_size.configure(text="")
        n = listbox.size()
        if n:
            new_idx = min(idx, n - 1)
            listbox.selection_set(new_idx)
            charger_image(new_idx)
        lbl_count.configure(text=f"{len(state['paths'])} image(s)")

    btn_del.configure(command=supprimer)


# ─────────────────────────────────────────────────────────────
#  Fenêtre principale
# ─────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("DicoImage — Pipeline PDF → Découpes")
    root.minsize(700, 660)

    style = ttk.Style()
    try:
        style.theme_use("clam")
        style.configure("Danger.TButton", foreground="red")
    except Exception:
        pass

    # Variables partagées entre l'onglet 1 et l'onglet Calibrer
    sv = {
        "pdf":     tk.StringVar(value="mon_livre.pdf"),
        "out_col": tk.StringVar(value="colonnes_droites"),
        "excl":    tk.StringVar(value="1,2,3,900"),
        "col_s":   tk.DoubleVar(value=2/3),
        "col_e":   tk.DoubleVar(value=1.0),
        "dpi":     tk.IntVar(value=300),
        "quality": tk.IntVar(value=85),
        "ml":      tk.IntVar(value=10),
        "mr":      tk.IntVar(value=10),
        "mt":      tk.IntVar(value=20),
        "mb":      tk.IntVar(value=20),
    }

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    build_tab_extract(nb, sv)
    build_tab_calibrer(nb, sv)
    build_tab_decoupe(nb)
    build_tab_affinage(nb)

    root.mainloop()


if __name__ == "__main__":
    main()
