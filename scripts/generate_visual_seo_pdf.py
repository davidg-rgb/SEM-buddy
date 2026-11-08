"""Generate a visual, easy-to-read SEO PDF report from seo_analysis.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle, Wedge
import numpy as np


COLOR_GOOD = "#10B981"
COLOR_WARN = "#F59E0B"
COLOR_BAD = "#EF4444"
COLOR_TEXT = "#1F2937"
COLOR_MUTED = "#6B7280"
COLOR_BG = "#F9FAFB"
COLOR_ACCENT = "#3B82F6"


def grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    if score >= 50: return "E"
    return "F"


def color_for(score: float) -> str:
    if score >= 80: return COLOR_GOOD
    if score >= 60: return COLOR_WARN
    return COLOR_BAD


def color_for_metric(value: float, good_max: float, bad_min: float) -> str:
    """Lower is better."""
    if value <= good_max: return COLOR_GOOD
    if value >= bad_min: return COLOR_BAD
    return COLOR_WARN


def draw_page1_dashboard(data: dict, out_path: Path) -> None:
    sc = data["scorecard"]
    overall = sc["overall_score"]
    cats = sc["category_scores"]
    issues = sc["issues"]

    sev_counts = {"high": 0, "medium": 0, "low": 0}
    for i in issues:
        sev_counts[i["severity"]] = sev_counts.get(i["severity"], 0) + 1

    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
    fig.suptitle("", y=0.98)

    # ---- Header ----
    ax_h = fig.add_axes([0.05, 0.91, 0.9, 0.07])
    ax_h.axis("off")
    ax_h.text(0, 0.7, "SEO-analys", fontsize=24, fontweight="bold", color=COLOR_TEXT)
    ax_h.text(0, 0.2, f"www.novapsykiatri.se  ·  30 sidor analyserade  ·  2026-04-30",
              fontsize=10, color=COLOR_MUTED)

    # ---- Overall score gauge ----
    ax_g = fig.add_axes([0.05, 0.66, 0.42, 0.22])
    ax_g.set_xlim(-1.2, 1.2)
    ax_g.set_ylim(-0.3, 1.2)
    ax_g.axis("off")
    ax_g.set_aspect("equal")

    # Background arc
    bg = Wedge((0, 0), 1.0, 0, 180, width=0.22, facecolor="#E5E7EB", edgecolor="none")
    ax_g.add_patch(bg)
    # Filled arc proportional to score
    score_angle = 180 * (overall / 100)
    fg = Wedge((0, 0), 1.0, 180 - score_angle, 180, width=0.22,
               facecolor=color_for(overall), edgecolor="none")
    ax_g.add_patch(fg)

    ax_g.text(0, 0.35, grade(overall), fontsize=48, fontweight="bold",
              ha="center", va="center", color=color_for(overall))
    ax_g.text(0, 0.05, f"{overall:.0f} / 100", fontsize=14, ha="center",
              va="center", color=COLOR_TEXT)
    ax_g.text(0, -0.15, "TOTALT BETYG", fontsize=9, ha="center",
              va="center", color=COLOR_MUTED, fontweight="bold")

    # ---- Issue summary cards ----
    ax_i = fig.add_axes([0.52, 0.66, 0.43, 0.22])
    ax_i.set_xlim(0, 3)
    ax_i.set_ylim(0, 2)
    ax_i.axis("off")

    cards = [
        ("KRITISKA", sev_counts["high"], COLOR_BAD),
        ("MEDEL", sev_counts["medium"], COLOR_WARN),
        ("LÅGA", sev_counts["low"], COLOR_MUTED),
    ]
    for idx, (label, count, col) in enumerate(cards):
        x = idx
        box = FancyBboxPatch((x + 0.05, 0.3), 0.9, 1.5,
                             boxstyle="round,pad=0.02,rounding_size=0.06",
                             facecolor="white", edgecolor=col, linewidth=2)
        ax_i.add_patch(box)
        ax_i.text(x + 0.5, 1.3, str(count), fontsize=28, fontweight="bold",
                  ha="center", va="center", color=col)
        ax_i.text(x + 0.5, 0.55, label, fontsize=8, ha="center",
                  va="center", color=COLOR_TEXT, fontweight="bold")

    ax_i.text(1.5, 1.92, "PROBLEM HITTADE", fontsize=10, ha="center",
              color=COLOR_TEXT, fontweight="bold")

    # ---- Category bars ----
    ax_c = fig.add_axes([0.05, 0.32, 0.9, 0.28])
    ax_c.set_facecolor(COLOR_BG)
    labels = [c["label"] for c in cats]
    scores = [c["score"] for c in cats]
    colors = [color_for(s) for s in scores]

    y_pos = np.arange(len(labels))
    bars = ax_c.barh(y_pos, scores, color=colors, height=0.55, edgecolor="none")
    ax_c.barh(y_pos, [100] * len(scores), color="#E5E7EB", height=0.55,
              zorder=0, edgecolor="none")
    ax_c.set_yticks(y_pos)
    ax_c.set_yticklabels(labels, fontsize=11, color=COLOR_TEXT)
    ax_c.set_xlim(0, 110)
    ax_c.set_xticks([0, 50, 70, 90, 100])
    ax_c.tick_params(axis="x", labelsize=8, colors=COLOR_MUTED)
    ax_c.invert_yaxis()
    ax_c.spines[["top", "right", "left", "bottom"]].set_visible(False)

    for i, (bar, s) in enumerate(zip(bars, scores)):
        ax_c.text(s + 2, bar.get_y() + bar.get_height() / 2,
                  f"{s:.0f}  {grade(s)}", va="center", fontsize=10,
                  fontweight="bold", color=color_for(s))

    ax_c.set_title("Poäng per kategori", fontsize=13, fontweight="bold",
                   color=COLOR_TEXT, loc="left", pad=12)

    # ---- Top findings text block ----
    ax_t = fig.add_axes([0.05, 0.04, 0.9, 0.24])
    ax_t.axis("off")
    ax_t.text(0, 1.0, "Sammanfattning", fontsize=13, fontweight="bold",
              color=COLOR_TEXT)

    summary = (
        "Webbplatsen får betyg B (82/100) baserat på 30 analyserade sidor. Schema-data och länkstruktur är\n"
        "perfekta (A), men prestanda och innehåll drar ner totalbetyget.\n\n"
        "Tre största problemen:\n"
        "  •  Sidans laddningstid är extremt hög — LCP 9,0s (mål: under 2,5s) och TBT 3,6s (mål: under 0,2s)\n"
        "  •  Korta titlar och dubblerade meta-beskrivningar på 14–16 sidor — påverkar CTR i sökresultaten\n"
        "  •  Stora mängder bilder saknar alt-text (31–75 per sida), vilket skadar bild-SEO och tillgänglighet\n\n"
        "Styrkor: Schema markup (LocalBusiness, Organization, WebSite) på alla 30 sidor, korrekt\n"
        "robots.txt + sitemap (105 URL:er), 5124 internlänkar, accessibility-score 95/100."
    )
    ax_t.text(0, 0.92, summary, fontsize=9.5, color=COLOR_TEXT,
              va="top", linespacing=1.5)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()


def draw_page2_performance(data: dict, out_path: Path) -> None:
    lh = data["lighthouse"]
    cwv = lh["core_web_vitals"]

    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")

    # Header
    ax_h = fig.add_axes([0.05, 0.93, 0.9, 0.05])
    ax_h.axis("off")
    ax_h.text(0, 0.5, "Prestanda & Core Web Vitals", fontsize=20,
              fontweight="bold", color=COLOR_TEXT)

    # ---- Lighthouse score gauges ----
    lh_scores = [
        ("Prestanda", lh["performance_score"]),
        ("Tillgänglighet", lh["accessibility_score"]),
        ("Bästa praxis", lh["best_practices_score"]),
        ("SEO", lh["seo_score"]),
    ]

    for idx, (label, score) in enumerate(lh_scores):
        x_left = 0.05 + idx * 0.235
        ax = fig.add_axes([x_left, 0.74, 0.21, 0.16])
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-0.5, 1.2)
        ax.axis("off")
        ax.set_aspect("equal")

        bg = Wedge((0, 0), 1.0, 0, 180, width=0.25,
                   facecolor="#E5E7EB", edgecolor="none")
        ax.add_patch(bg)
        if score is not None:
            angle = 180 * (score / 100)
            fg = Wedge((0, 0), 1.0, 180 - angle, 180, width=0.25,
                       facecolor=color_for(score), edgecolor="none")
            ax.add_patch(fg)
            ax.text(0, 0.25, f"{score:.0f}", fontsize=22, fontweight="bold",
                    ha="center", va="center", color=color_for(score))
        else:
            ax.text(0, 0.25, "—", fontsize=22, fontweight="bold",
                    ha="center", va="center", color=COLOR_MUTED)
        ax.text(0, -0.15, label, fontsize=9, ha="center", va="center",
                color=COLOR_TEXT, fontweight="bold")

    # Section divider
    ax_sec = fig.add_axes([0.05, 0.69, 0.9, 0.02])
    ax_sec.axis("off")
    ax_sec.text(0, 0.5, "Core Web Vitals (Googles rankingfaktorer)",
                fontsize=13, fontweight="bold", color=COLOR_TEXT)

    # ---- CWV bars ----
    cwv_data = [
        ("LCP", cwv.get("lcp_ms", 0) or 0, 2500, "ms",
         "Largest Contentful Paint", 4000),
        ("TBT", cwv.get("tbt_ms", 0) or 0, 200, "ms",
         "Total Blocking Time", 600),
        ("FCP", cwv.get("fcp_ms", 0) or 0, 1800, "ms",
         "First Contentful Paint", 3000),
        ("CLS", cwv.get("cls", 0) or 0, 0.1, "",
         "Cumulative Layout Shift", 0.25),
        ("TTFB", cwv.get("ttfb_ms", 0) or 0, 800, "ms",
         "Time to First Byte", 1800),
    ]

    ax = fig.add_axes([0.05, 0.34, 0.9, 0.34])
    ax.set_facecolor("white")
    ax.set_xlim(0, 12)
    ax.set_ylim(0, len(cwv_data))
    ax.axis("off")

    for idx, (key, val, good_max, unit, full, bad_min) in enumerate(cwv_data):
        y = len(cwv_data) - 1 - idx + 0.5

        col = color_for_metric(val, good_max, bad_min)
        status = "✓" if val <= good_max else ("⚠" if val < bad_min else "✗")

        # Metric label
        ax.text(0, y, key, fontsize=14, fontweight="bold",
                color=COLOR_TEXT, va="center")
        ax.text(1.0, y, full, fontsize=9, color=COLOR_MUTED, va="center")

        # Status icon
        ax.text(11.5, y, status, fontsize=16, fontweight="bold",
                color=col, va="center", ha="center")

        # Value
        if unit == "ms":
            v_str = f"{val:.0f} {unit}"
            target_str = f"mål: ≤{good_max} ms"
        elif key == "CLS":
            v_str = f"{val:.3f}"
            target_str = f"mål: ≤{good_max}"
        else:
            v_str = f"{val:.0f}{unit}"
            target_str = f"mål: ≤{good_max}{unit}"

        ax.text(7.5, y + 0.18, v_str, fontsize=12, fontweight="bold",
                color=col, va="center", ha="right")
        ax.text(7.5, y - 0.18, target_str, fontsize=8, color=COLOR_MUTED,
                va="center", ha="right")

        # Mini bar visualization (relative to bad_min boundary)
        bar_max = bad_min * 1.2
        bar_x = 7.8
        bar_w = 3.4
        ax.add_patch(Rectangle((bar_x, y - 0.15), bar_w, 0.3,
                               facecolor="#E5E7EB", edgecolor="none"))
        # Good zone
        good_w = bar_w * (good_max / bar_max)
        ax.add_patch(Rectangle((bar_x, y - 0.15), good_w, 0.3,
                               facecolor=COLOR_GOOD, alpha=0.18,
                               edgecolor="none"))
        # Actual value marker
        actual_w = min(bar_w, bar_w * (val / bar_max))
        ax.add_patch(Rectangle((bar_x, y - 0.06), actual_w, 0.12,
                               facecolor=col, edgecolor="none"))

    # ---- Diagnosis text ----
    ax_d = fig.add_axes([0.05, 0.04, 0.9, 0.27])
    ax_d.axis("off")
    ax_d.text(0, 1.0, "Diagnos", fontsize=13, fontweight="bold", color=COLOR_TEXT)

    diag_text = (
        "Servern svarar snabbt (TTFB 209 ms) och layouten är stabil (CLS 0.000), så problemet ligger\n"
        "uteslutande i frontend: tunga JS-bundles och ooptimerade bilder.\n\n"
        "Lighthouse identifierade tre största besparingar:\n"
        "  1.  Reducera oanvänd JavaScript               besparing  ~1300 ms\n"
        "  2.  Reducera oanvänd CSS                       besparing   ~980 ms\n"
        "  3.  Minifiera JavaScript                       besparing   ~330 ms\n\n"
        "Detta är ett typiskt mönster för Wix-sajter — varje installerad app eller widget lägger till JS som\n"
        "blockerar huvudtråden. Förbättring kräver: optimera hero-bilden (WebP, < 200 KB),\n"
        "avinstallera oanvända Wix-appar, defer/async tredjepartsskript, aktivera lazy loading."
    )
    ax_d.text(0, 0.92, diag_text, fontsize=9.5, color=COLOR_TEXT,
              va="top", linespacing=1.5, family="DejaVu Sans Mono")

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()


def draw_page3_critical(data: dict, out_path: Path) -> None:
    issues = data["scorecard"]["issues"]
    high = [i for i in issues if i["severity"] == "high"]

    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")

    ax_h = fig.add_axes([0.05, 0.93, 0.9, 0.05])
    ax_h.axis("off")
    ax_h.text(0, 0.5, "Kritiska problem", fontsize=20,
              fontweight="bold", color=COLOR_TEXT)
    ax_h.text(0, -0.5, f"{len(high)} problem som kräver omedelbar åtgärd",
              fontsize=10, color=COLOR_MUTED)

    # Render up to 4 critical issues as cards
    n = min(4, len(high))
    card_h = 0.20
    gap = 0.02
    start_y = 0.88
    for idx, issue in enumerate(high[:n]):
        y = start_y - (idx + 1) * card_h - idx * gap
        ax = fig.add_axes([0.05, y, 0.9, card_h])
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis("off")

        # Card background
        ax.add_patch(FancyBboxPatch((0.05, 0.2), 9.9, 9.6,
                                     boxstyle="round,pad=0,rounding_size=0.15",
                                     facecolor="white",
                                     edgecolor=COLOR_BAD, linewidth=1.5))
        # Severity badge
        ax.add_patch(FancyBboxPatch((0.3, 8), 1.4, 1.3,
                                     boxstyle="round,pad=0,rounding_size=0.2",
                                     facecolor=COLOR_BAD, edgecolor="none"))
        ax.text(1.0, 8.65, "KRITISK", fontsize=8, color="white",
                ha="center", va="center", fontweight="bold")

        # Title
        ax.text(2.0, 8.65, issue["title"], fontsize=12, fontweight="bold",
                color=COLOR_TEXT, va="center")

        # Description
        desc = issue["description"]
        if len(desc) > 130:
            desc = desc[:127] + "..."
        ax.text(0.3, 7, desc, fontsize=9.5, color=COLOR_TEXT, va="top",
                wrap=True)

        # Affected URLs
        urls = issue.get("affected_urls", [])
        if urls:
            url_str = ", ".join(u.replace("https://www.novapsykiatri.se", "")
                                or "/" for u in urls[:3])
            if len(urls) > 3:
                url_str += f"  +{len(urls) - 3} till"
            ax.text(0.3, 5.0, "Berörda sidor: " + url_str,
                    fontsize=8.5, color=COLOR_MUTED, va="top")

        # Fix
        fix = issue.get("fix_suggestion", "")
        if len(fix) > 130:
            fix = fix[:127] + "..."
        ax.text(0.3, 3.5, "→ " + fix, fontsize=9, color=COLOR_ACCENT,
                va="top", fontweight="bold")

        # Effort
        effort = issue.get("effort", "")
        eff_label = {"low": "Låg insats", "medium": "Medel insats",
                     "high": "Hög insats"}.get(effort, effort)
        eff_color = {"low": COLOR_GOOD, "medium": COLOR_WARN,
                     "high": COLOR_BAD}.get(effort, COLOR_MUTED)
        ax.text(9.7, 1.0, eff_label, fontsize=8.5, color=eff_color,
                ha="right", va="center", fontweight="bold")

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()


def draw_page4_action_plan(data: dict, out_path: Path) -> None:
    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")

    ax_h = fig.add_axes([0.05, 0.93, 0.9, 0.05])
    ax_h.axis("off")
    ax_h.text(0, 0.5, "Handlingsplan", fontsize=20,
              fontweight="bold", color=COLOR_TEXT)
    ax_h.text(0, -0.5, "Prioriterade åtgärder sorterade efter effekt och insats",
              fontsize=10, color=COLOR_MUTED)

    # Three priority sections
    sections = [
        ("STEG 1 — PRESTANDA", "Störst SEO-påverkan just nu", COLOR_BAD,
         [
             "Komprimera hero-bilden, byt till WebP, max 200 KB, ange width/height",
             "Avinstallera oanvända Wix-appar (varje app = mer JS-tyngd)",
             "Defer/async alla tredjepartsskript (analytics, chat, widgets)",
             "Aktivera Wix CDN och lazy loading-inställningar",
             "Reducera oanvänd CSS och JavaScript (Lighthouse identifierade ~2,6s besparing)",
         ]),
        ("STEG 2 — ON-PAGE SEO", "Snabba vinster, låg insats", COLOR_WARN,
         [
             "Skriv H1 + meta description på /cart, /webbinarium, /fri-radgivning",
             "Skriv unika titlar (50–60 tecken) på de 14 sidorna med duplicerade titlar",
             "Skriv unika meta-beskrivningar (120–160 tecken) på de 16 sidorna med dubbletter",
             "Förkorta omdirigeringskedja (2 steg → 1 steg)",
             "Korrigera bruten rubrikhierarki (H1 → H2 → H3 utan att hoppa över nivåer)",
         ]),
        ("STEG 3 — INNEHÅLL & TILLGÄNGLIGHET", "Långsiktig optimering", COLOR_ACCENT,
         [
             "Lägg till alt-text på alla innehållsbilder (kan göras massvis i Wix media-bibliotek)",
             "Utöka tunna sidor till minst 300 ord: /cart, /media, /kontakt, /var-vi-finns",
             "Komplettera Open Graph-taggar (og:title, og:description, og:image)",
             "Granska duplicerad title-mall och unika H1 på menu-sidorna",
         ]),
    ]

    section_h = 0.27
    gap = 0.015
    start_y = 0.88

    for s_idx, (title, subtitle, color, items) in enumerate(sections):
        y = start_y - (s_idx + 1) * section_h - s_idx * gap
        ax = fig.add_axes([0.05, y, 0.9, section_h])
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis("off")

        # Left color stripe
        ax.add_patch(Rectangle((0, 0.3), 0.15, 9.4,
                                facecolor=color, edgecolor="none"))
        # Card background
        ax.add_patch(FancyBboxPatch((0.2, 0.3), 9.78, 9.4,
                                     boxstyle="round,pad=0,rounding_size=0.1",
                                     facecolor=COLOR_BG, edgecolor="none"))

        # Title
        ax.text(0.4, 8.8, title, fontsize=11, fontweight="bold", color=color,
                va="center")
        ax.text(0.4, 7.7, subtitle, fontsize=9, color=COLOR_MUTED, va="center",
                style="italic")

        # Items
        item_y_start = 6.8
        for i, item in enumerate(items):
            iy = item_y_start - i * 1.2
            if iy < 0.5:
                break
            ax.text(0.5, iy, "□", fontsize=11, color=color, va="center")
            ax.text(0.95, iy, item, fontsize=9, color=COLOR_TEXT,
                    va="center", wrap=True)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()


def combine_pages_to_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    """Combine multiple PNG pages into a single PDF using matplotlib."""
    from matplotlib.backends.backend_pdf import PdfPages
    from PIL import Image

    with PdfPages(str(pdf_path)) as pdf:
        for img_path in image_paths:
            img = Image.open(img_path)
            w, h = img.size
            fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
            ax = fig.add_axes([0, 0, 1, 1])
            ax.imshow(img)
            ax.axis("off")
            pdf.savefig(fig, dpi=150)
            plt.close(fig)


def main() -> None:
    json_path = Path("clients/novapsykiatri/seo/seo_analysis.json")
    out_dir = Path("clients/novapsykiatri/seo")
    pdf_path = out_dir / "seo_visual_report.pdf"

    data = json.loads(json_path.read_text(encoding="utf-8"))

    tmp_dir = out_dir / "_tmp_pages"
    tmp_dir.mkdir(exist_ok=True)

    pages = []
    p1 = tmp_dir / "page1.png"
    p2 = tmp_dir / "page2.png"
    p3 = tmp_dir / "page3.png"
    p4 = tmp_dir / "page4.png"

    print("Rendering page 1: Dashboard...")
    draw_page1_dashboard(data, p1)
    print("Rendering page 2: Performance...")
    draw_page2_performance(data, p2)
    print("Rendering page 3: Critical issues...")
    draw_page3_critical(data, p3)
    print("Rendering page 4: Action plan...")
    draw_page4_action_plan(data, p4)

    pages = [p1, p2, p3, p4]

    print(f"Combining into PDF: {pdf_path}")
    combine_pages_to_pdf(pages, pdf_path)

    # Cleanup
    for p in pages:
        p.unlink(missing_ok=True)
    tmp_dir.rmdir()

    print(f"Done: {pdf_path.resolve()}")


if __name__ == "__main__":
    main()
