"""
Kleines Hilfsskript, um Platzhalter-PNGs fuer die README zu erzeugen.
Ausfuehren mit:

    python3 docs/screenshots/_generate_placeholders.py

Die erzeugten Dateien sind nur Platzhalter. Sobald echte Screenshots
vorliegen, einfach mit identischem Dateinamen ersetzen.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent

ACCENT = (88, 166, 255)  # GitHub-Blau

DARK = {
    "bg":     (13, 17, 23),
    "panel":  (22, 27, 34),
    "elev":   (30, 35, 44),
    "border": (48, 54, 61),
    "fg":     (230, 237, 243),
    "muted":  (139, 148, 158),
    "faint":  (110, 118, 129),
}
LIGHT = {
    "bg":     (246, 248, 250),
    "panel":  (255, 255, 255),
    "elev":   (234, 238, 242),
    "border": (208, 215, 222),
    "fg":     (31, 35, 40),
    "muted":  (87, 96, 106),
    "faint":  (130, 140, 150),
}


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    # Fallback, falls Helvetica-Varianten nicht da sind
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def measure(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont):
    box = draw.textbbox((0, 0), text, font=f)
    return box[2] - box[0], box[3] - box[1]


def draw_header(draw, w, palette, title_left: str):
    draw.rectangle([(0, 0), (w, 52)], fill=palette["panel"])
    draw.line([(0, 52), (w, 52)], fill=palette["border"], width=1)
    # "Logo"-Punkt + App-Name
    draw.ellipse([(16, 16), (36, 36)], fill=ACCENT)
    f = font(16, bold=True)
    draw.text((46, 16), "CuttOffl", fill=palette["fg"], font=f)
    f2 = font(12)
    draw.text((125, 20), title_left, fill=palette["muted"], font=f2)


def draw_sidebar(draw, x0, y0, w, h, palette, active_label: str):
    draw.rectangle([(x0, y0), (x0 + w, y0 + h)], fill=palette["panel"])
    draw.line([(x0 + w, y0), (x0 + w, y0 + h)], fill=palette["border"])
    items = ["Dashboard", "Bibliothek", "Editor",
             "Fertige Videos", "Einstellungen", "Über"]
    f = font(13)
    for i, item in enumerate(items):
        y = y0 + 24 + i * 36
        if item == active_label:
            draw.rounded_rectangle([(x0 + 12, y - 6), (x0 + w - 12, y + 22)],
                                   radius=6, fill=palette["elev"])
            draw.text((x0 + 26, y), item, fill=ACCENT, font=f)
        else:
            draw.text((x0 + 26, y), item, fill=palette["muted"], font=f)


def draw_stamp(draw, w, h, palette, subtitle: str):
    # Dezenter "Platzhalter"-Stempel, damit niemand die Datei mit einem
    # echten Screenshot verwechselt.
    f_big = font(42, bold=True)
    f_small = font(16)
    label = "Screenshot folgt"
    tw, th = measure(draw, label, f_big)
    cx, cy = w // 2, h // 2 + 10
    draw.text((cx - tw // 2, cy - th // 2 - 18), label,
              fill=palette["fg"], font=f_big)
    sw, sh = measure(draw, subtitle, f_small)
    draw.text((cx - sw // 2, cy + th // 2 - 14), subtitle,
              fill=palette["muted"], font=f_small)


def skeleton_timeline(draw, x, y, w, h, palette):
    # Timeline-Area
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=6,
                           fill=palette["elev"], outline=palette["border"])
    # Thumbnail-Streifen
    tiles = 18
    tw = (w - 20) / tiles
    for i in range(tiles):
        tx = x + 10 + int(i * tw)
        draw.rectangle([(tx, y + 10), (tx + int(tw) - 2, y + 40)],
                       fill=palette["border"])
    # Keyframe-Marker
    for i in range(5):
        kx = x + 30 + i * int((w - 60) / 4)
        draw.line([(kx, y + 6), (kx, y + h - 6)], fill=ACCENT, width=2)
    # Clip-Box
    draw.rounded_rectangle(
        [(x + 60, y + 52), (x + int(w * 0.45), y + 80)],
        radius=4, fill=ACCENT,
    )
    draw.rounded_rectangle(
        [(x + int(w * 0.52), y + 52), (x + int(w * 0.85), y + 80)],
        radius=4, fill=(46, 160, 67),  # gruen = copy
    )
    # Wellenform (kleine Sinus-artige Balken)
    import math
    for i in range(w - 20):
        xx = x + 10 + i
        a = int(8 + 8 * abs(math.sin(i * 0.05) + math.sin(i * 0.017) * 0.4))
        cy = y + h - 18
        draw.line([(xx, cy - a), (xx, cy + a)], fill=palette["faint"])


def skeleton_library_tiles(draw, x, y, cols, rows, tile_w, tile_h, gap, palette, dark: bool):
    for r in range(rows):
        for c in range(cols):
            tx = x + c * (tile_w + gap)
            ty = y + r * (tile_h + gap)
            draw.rounded_rectangle([(tx, ty), (tx + tile_w, ty + tile_h)],
                                   radius=8, fill=palette["panel"],
                                   outline=palette["border"])
            # Thumbnail-Bereich
            draw.rectangle([(tx, ty), (tx + tile_w, ty + int(tile_h * 0.55))],
                           fill=palette["elev"])
            draw.rounded_rectangle(
                [(tx + tile_w - 68, ty + 8), (tx + tile_w - 8, ty + 22)],
                radius=7, fill=(46, 160, 67),
            )
            # Namens-Linien
            for i in range(2):
                yy = ty + int(tile_h * 0.60) + i * 14
                draw.line([(tx + 12, yy), (tx + tile_w - 12 - i * 40, yy)],
                          fill=palette["border"], width=2)
            # Tag-Chips
            draw.rounded_rectangle(
                [(tx + 12, ty + int(tile_h * 0.85)),
                 (tx + 58, ty + int(tile_h * 0.85) + 14)],
                radius=7, fill=ACCENT,
            )
            draw.rounded_rectangle(
                [(tx + 64, ty + int(tile_h * 0.85)),
                 (tx + 118, ty + int(tile_h * 0.85) + 14)],
                radius=7, fill=(210, 153, 34),
            )


def skeleton_dashboard(draw, x, y, w, h, palette):
    # 4 KPI-Kacheln
    kpi_w = (w - 30) // 4
    for i in range(4):
        kx = x + i * (kpi_w + 10)
        draw.rounded_rectangle([(kx, y), (kx + kpi_w, y + 110)],
                               radius=8, fill=palette["panel"],
                               outline=palette["border"])
        draw.line([(kx + 16, y + 28), (kx + 70, y + 28)],
                  fill=palette["muted"], width=2)
        draw.rounded_rectangle([(kx + 16, y + 48), (kx + 80, y + 78)],
                               radius=4, fill=ACCENT)
    # Speicher-Panel
    draw.rounded_rectangle([(x, y + 130), (x + w, y + 330)],
                           radius=8, fill=palette["panel"],
                           outline=palette["border"])
    for i in range(5):
        yy = y + 160 + i * 30
        draw.line([(x + 20, yy), (x + 140, yy)], fill=palette["muted"], width=2)
        draw.rounded_rectangle(
            [(x + 180, yy - 6), (x + 180 + (w - 220) * (0.8 - i * 0.12), yy + 6)],
            radius=6, fill=ACCENT,
        )


def make(name: str, w: int, h: int, palette: dict, dark: bool,
         title: str, subtitle: str, active_label: str, kind: str):
    img = Image.new("RGB", (w, h), palette["bg"])
    d = ImageDraw.Draw(img)
    draw_header(d, w, palette, title)

    sb_w = 180
    draw_sidebar(d, 0, 52, sb_w, h - 52, palette, active_label)

    # Content-Bereich
    pad = 20
    cx = sb_w + pad
    cy = 52 + pad
    cw = w - sb_w - pad * 2
    ch = h - 52 - pad * 2

    if kind == "editor":
        # Player + Timeline
        player_h = int(ch * 0.55)
        d.rounded_rectangle([(cx, cy), (cx + cw, cy + player_h)],
                            radius=8, fill=(0, 0, 0),
                            outline=palette["border"])
        d.rounded_rectangle(
            [(cx + cw // 2 - 34, cy + player_h // 2 - 34),
             (cx + cw // 2 + 34, cy + player_h // 2 + 34)],
            radius=40, fill=ACCENT,
        )
        # Play-Dreieck
        cx0 = cx + cw // 2 - 10
        cy0 = cy + player_h // 2
        d.polygon([(cx0, cy0 - 16), (cx0, cy0 + 16), (cx0 + 22, cy0)],
                  fill=(255, 255, 255))
        skeleton_timeline(d, cx, cy + player_h + 16, cw, ch - player_h - 16, palette)

    elif kind == "timeline":
        skeleton_timeline(d, cx, cy + ch // 4, cw, ch // 2, palette)

    elif kind == "library":
        # Toolbar + Kacheln
        d.rounded_rectangle([(cx, cy), (cx + cw, cy + 40)], radius=6,
                            fill=palette["panel"], outline=palette["border"])
        for i, label_w in enumerate([80, 60, 80, 120, 100, 100]):
            xx = cx + 12 + sum([80, 60, 80, 120, 100, 100][:i]) + i * 10
            d.rounded_rectangle([(xx, cy + 10), (xx + label_w, cy + 30)],
                                radius=4, fill=palette["elev"])
        tile_w = (cw - 20) // 3
        tile_h = 200
        skeleton_library_tiles(d, cx, cy + 56, 3, 2, tile_w, tile_h, 12, palette, dark)

    elif kind == "dashboard":
        skeleton_dashboard(d, cx, cy, cw, ch, palette)

    # Sanfter "Platzhalter"-Stempel, mittig
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    draw_stamp(od, w, h, palette, subtitle)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    out = OUT / name
    img.save(out, "PNG", optimize=True)
    print(f"  wrote {out.name}  ({w}x{h})")


def main() -> None:
    print("Erzeuge Platzhalter-PNGs ...")
    # Hero: 16:9, etwas breiter
    make("hero-editor-dark.png", 1760, 990, DARK, True,
         "Editor", "Editor in Aktion, Dark-Modus",
         active_label="Editor", kind="editor")
    make("editor-timeline.png", 1200, 675, DARK, True,
         "Editor > Timeline", "Keyframes, Thumbnail-Streifen, Wellenform",
         active_label="Editor", kind="timeline")
    make("dashboard.png", 1200, 750, DARK, True,
         "Dashboard", "KPIs, Speicher, Codec-Empfehlung",
         active_label="Dashboard", kind="dashboard")
    make("library.png", 1200, 750, DARK, True,
         "Bibliothek", "Ordner, Kacheln, Tags, Filter",
         active_label="Bibliothek", kind="library")
    make("editor-light.png", 1200, 675, LIGHT, False,
         "Editor", "Gleiche Szene, Hell-Modus",
         active_label="Editor", kind="editor")
    print("Fertig. Die Dateien sind nur Platzhalter -- bitte durch echte")
    print("Screenshots mit identischem Namen ersetzen.")


if __name__ == "__main__":
    main()
