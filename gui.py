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

    v_filter = tk.StringVar(value="tous")
    filter_bar = ttk.Frame(frame)
    filter_bar.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
    for text, val in [("Tous", "tous"), ("Blocs", "blocs"), ("Lignes", "lignes")]:
        ttk.Radiobutton(filter_bar, text=text, variable=v_filter, value=val,
                        command=lambda: appliquer_filtre()).pack(side="left", padx=6)

    # ── Panneau gauche : liste ─────────────────────────────
    left = ttk.Frame(frame)
    frame.rowconfigure(2, weight=1)
    left.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
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
    right.grid(row=2, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(0, weight=1)

    canvas = tk.Canvas(right, width=CANVAS_W2, height=CANVAS_H2,
                       bg="#1e1e1e", relief="sunken", bd=1)
    canvas.grid(row=0, column=0, sticky="nsew")

    ctrl = ttk.Frame(right)
    ctrl.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    ctrl.columnconfigure(1, weight=1)
    ctrl.columnconfigure(5, weight=1)

    state = {
        "img": None, "path": None, "tk_ref": None,
        "all_paths": [], "paths": [],
        "scale": 1.0, "off_x": 0, "off_y": 0, "disp_w": 0, "disp_h": 0,
        "split_lines": [],   # Y coords dans l'image originale
        "split_mode": False,
    }

    v_top = tk.IntVar(value=0)
    v_bot = tk.IntVar(value=0)
    v_lft = tk.IntVar(value=0)
    v_rgt = tk.IntVar(value=0)

    lbl_size = ttk.Label(right, text="", foreground="gray", anchor="center")
    lbl_size.grid(row=2, column=0, sticky="ew")

    # ── Refresh canvas ─────────────────────────────────────
    def refresh_canvas(*_):
        img = state["img"]
        if img is None:
            return
        preview = make_crop_preview(img, v_top.get(), v_bot.get(),
                                    v_lft.get(), v_rgt.get())
        w_img, h_img = preview.size
        scale = min(CANVAS_W2 / w_img, CANVAS_H2 / h_img)
        new_w, new_h = int(w_img * scale), int(h_img * scale)
        fitted = preview.resize((new_w, new_h), Image.LANCZOS)

        off_x = (CANVAS_W2 - new_w) // 2
        off_y = (CANVAS_H2 - new_h) // 2
        state.update(scale=scale, off_x=off_x, off_y=off_y,
                     disp_w=new_w, disp_h=new_h)

        tk_img = ImageTk.PhotoImage(fitted)
        state["tk_ref"] = tk_img
        canvas.delete("all")
        canvas.create_image(off_x, off_y, anchor="nw", image=tk_img)

        # Lignes de scission
        for iy in state["split_lines"]:
            cy = off_y + int(iy * scale)
            canvas.create_line(off_x, cy, off_x + new_w, cy,
                               fill="#FFB300", width=2, dash=(6, 3), tags="split")

    # ── Sliders crop ───────────────────────────────────────
    s_top = s_bot = s_lft = s_rgt = None

    def make_slider(label, var, row, col_offset=0):
        c = col_offset
        ttk.Label(ctrl, text=label).grid(row=row, column=c, sticky="w", pady=3)
        val_lbl = ttk.Label(ctrl, text="0", width=4, anchor="e")
        val_lbl.grid(row=row, column=c + 2, padx=(2, 8))

        def on_change(*_):
            var.set(int(var.get()))
            val_lbl.configure(text=str(var.get()))
            refresh_canvas()

        s = ttk.Scale(ctrl, from_=0, to=200, variable=var,
                      orient="horizontal", command=on_change)
        s.grid(row=row, column=c + 1, sticky="ew", padx=4)
        return s, val_lbl

    s_top, lv_top = make_slider("Haut",   v_top, 0, col_offset=0)
    s_bot, lv_bot = make_slider("Bas",    v_bot, 1, col_offset=0)
    s_lft, lv_lft = make_slider("Gauche", v_lft, 0, col_offset=4)
    s_rgt, lv_rgt = make_slider("Droite", v_rgt, 1, col_offset=4)

    # ── Barre scission ─────────────────────────────────────
    split_bar = ttk.Frame(right)
    split_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
    split_bar.columnconfigure(0, weight=1)
    split_bar.columnconfigure(1, weight=1)
    split_bar.columnconfigure(2, weight=1)

    btn_mode  = ttk.Button(split_bar, text="✂  Mode scission")
    btn_clear = ttk.Button(split_bar, text="Effacer lignes")
    btn_split = ttk.Button(split_bar, text="Scinder")
    btn_mode .grid(row=0, column=0, sticky="ew", padx=(0, 4))
    btn_clear.grid(row=0, column=1, sticky="ew", padx=4)
    btn_split.grid(row=0, column=2, sticky="ew", padx=(4, 0))

    btn_save = ttk.Button(right, text="Sauvegarder le crop  →  image suivante")
    btn_save.grid(row=4, column=0, sticky="ew", pady=(6, 0))

    # ── Mode scission toggle ───────────────────────────────
    def toggle_split_mode():
        state["split_mode"] = not state["split_mode"]
        if state["split_mode"]:
            btn_mode.configure(text="✂  Mode scission  ●")
            canvas.configure(cursor="crosshair")
        else:
            btn_mode.configure(text="✂  Mode scission")
            canvas.configure(cursor="")

    btn_mode.configure(command=toggle_split_mode)

    def effacer_lignes():
        state["split_lines"].clear()
        refresh_canvas()

    btn_clear.configure(command=effacer_lignes)

    # ── Clic sur le canvas (pose/retire une ligne) ─────────
    def on_canvas_click(event):
        if not state["split_mode"] or state["img"] is None:
            return
        off_x = state["off_x"]
        off_y = state["off_y"]
        disp_w = state["disp_w"]
        disp_h = state["disp_h"]
        scale  = state["scale"]

        if not (off_x <= event.x <= off_x + disp_w and
                off_y <= event.y <= off_y + disp_h):
            return

        iy = int((event.y - off_y) / scale)
        h_img = state["img"].size[1]
        iy = max(1, min(h_img - 1, iy))

        # Retirer si proche d'une ligne existante
        thresh = max(3, int(5 / scale))
        for existing in list(state["split_lines"]):
            if abs(existing - iy) <= thresh:
                state["split_lines"].remove(existing)
                refresh_canvas()
                return

        state["split_lines"].append(iy)
        state["split_lines"].sort()
        refresh_canvas()

    canvas.bind("<Button-1>", on_canvas_click)

    # ── Scinder ────────────────────────────────────────────
    def scinder():
        img   = state["img"]
        path  = state["path"]
        lines = state["split_lines"]
        if img is None or path is None:
            return
        if not lines:
            messagebox.showinfo("Scinder",
                "Aucune ligne posée.\nCliquez sur l'image en mode scission.")
            return

        w, h  = img.size
        cuts  = [0] + sorted(lines) + [h]
        folder = Path(v_folder.get())
        stem, suffix = path.stem, path.suffix

        new_paths = []
        for i, (y0, y1) in enumerate(zip(cuts, cuts[1:]), start=1):
            if y1 - y0 < 4:
                continue
            piece = img.crop((0, y0, w, y1)).convert("RGB")
            out_p = path.parent / f"{stem}_p{i:02d}{suffix}"
            piece.save(out_p, "JPEG", quality=85)
            new_paths.append(out_p)

        if not new_paths:
            messagebox.showerror("Erreur", "Aucun fragment valide généré.")
            return

        sel = listbox.curselection()
        idx = sel[0] if sel else state["paths"].index(path)
        path.unlink()
        state["paths"].pop(idx)
        listbox.delete(idx)

        for i, np_ in enumerate(new_paths):
            state["paths"].insert(idx + i, np_)
            try:
                rel = np_.relative_to(folder)
            except ValueError:
                rel = np_.name
            listbox.insert(idx + i, str(rel))

        state["split_lines"].clear()
        lbl_count.configure(text=f"{len(state['paths'])} image(s)")
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(idx)
        listbox.see(idx)
        charger_image(idx)

    btn_split.configure(command=scinder)

    # ── Navigation ─────────────────────────────────────────
    def go_to(idx):
        n = listbox.size()
        if n == 0 or idx < 0 or idx >= n:
            return
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(idx)
        listbox.see(idx)
        charger_image(idx)

    # ── Chargement dossier ─────────────────────────────────
    def appliquer_filtre():
        folder  = Path(v_folder.get())
        filtre  = v_filter.get()
        all_p   = state["all_paths"]
        if filtre == "blocs":
            paths = [p for p in all_p if "blocs" in p.parts]
        elif filtre == "lignes":
            paths = [p for p in all_p if "lignes" in p.parts]
        else:
            paths = list(all_p)
        state["paths"] = paths
        listbox.delete(0, tk.END)
        for p in paths:
            try:
                rel = p.relative_to(folder)
            except ValueError:
                rel = p.name
            listbox.insert(tk.END, str(rel))
        lbl_count.configure(text=f"{len(paths)} image(s)")
        if paths:
            go_to(0)
        else:
            state.update(img=None, path=None)
            canvas.delete("all")
            lbl_size.configure(text="")

    def charger_dossier():
        folder = Path(v_folder.get())
        if not folder.exists():
            messagebox.showerror("Erreur", f"Dossier introuvable :\n{folder}")
            return
        exts = ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG")
        paths = [p for ext in exts for p in sorted(folder.rglob(ext))]
        seen = set()
        paths = [p for p in paths if not (p in seen or seen.add(p))]
        state["all_paths"] = paths
        appliquer_filtre()

    btn_charger.configure(command=charger_dossier)

    # ── Chargement image ───────────────────────────────────
    def charger_image(idx):
        paths = state["paths"]
        if not paths or idx >= len(paths):
            return
        path = paths[idx]
        img  = Image.open(path)
        state.update(img=img, path=path, split_lines=[])
        w, h = img.size
        lbl_size.configure(text=f"{path.name}  •  {w}×{h} px")
        for var, lv in [(v_top, lv_top), (v_bot, lv_bot),
                        (v_lft, lv_lft), (v_rgt, lv_rgt)]:
            var.set(0)
            lv.configure(text="0")
        for sl in (s_top, s_bot):
            sl.configure(to=max(1, min(h // 2, 400)))
        for sl in (s_lft, s_rgt):
            sl.configure(to=max(1, w // 2))
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
        if event.keysym == "Down":
            go_to(idx + 1)
        elif event.keysym == "Up":
            go_to(idx - 1)

    listbox.bind("<KeyPress>", on_key)

    # ── Sauvegarder + passer au suivant ───────────────────
    def sauvegarder():
        img  = state["img"]
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

        sel = listbox.curselection()
        idx = sel[0] if sel else 0
        lbl_size.configure(
            text=f"{path.name}  •  {cropped.size[0]}×{cropped.size[1]} px  ✓")

        # Avancer à l'image suivante
        if idx + 1 < listbox.size():
            go_to(idx + 1)
        else:
            state["img"] = Image.open(path)
            refresh_canvas()

    btn_save.configure(command=sauvegarder)

    # ── Supprimer ─────────────────────────────────────────
    def supprimer():
        path = state["path"]
        sel  = listbox.curselection()
        if path is None or not sel:
            return
        if not messagebox.askyesno("Supprimer",
                                   f"Supprimer définitivement :\n{path.name} ?"):
            return
        idx = sel[0]
        path.unlink()
        state["paths"].pop(idx)
        listbox.delete(idx)
        state.update(img=None, path=None)
        canvas.delete("all")
        lbl_size.configure(text="")
        n = listbox.size()
        if n:
            go_to(min(idx, n - 1))
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
