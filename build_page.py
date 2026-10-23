"""Turns results.json (+ your notes.md) into a static page in site/, ready for Vercel."""
import html, json, pathlib, re
from PIL import Image

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
LINE_COLORS = ["#2B3FD6", "#B5462E"]  # validated for contrast and colorblind separation on #E7E6DC
ROLE_LABEL = {"background": "Background", "accent": "Accent", "text": "Text"}


def esc(s):
    return html.escape(str(s))


def export_images(runs):
    (SITE / "img").mkdir(parents=True, exist_ok=True)
    for n, steps in enumerate(runs, 1):
        for s in steps:
            name = f"run{n}-round{s['round']}.jpg"
            img = Image.open(ROOT / s["image"]).convert("RGB")
            img.thumbnail((900, 900))
            img.save(SITE / "img" / name, quality=84, optimize=True)
            s["web"] = f"img/{name}"


def short_font(text, limit=48):
    """The AI's font notes run long; show the first font it actually named."""
    t = str(text)
    m = re.search(r"(?:similar to|resembling|resembles|like)\s+'?([A-Z][\w ]*?[\w])'?\s*(?:,|\bor\b|\(|\.|;|$)", t)
    if m:
        return re.split(r"\s+or\s*(?=[A-Z])", m.group(1))[0]
    t = t.split(";")[0].split(". ")[0].strip()
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + "…"


def swatch(hx):
    return f'<span class="chip" style="background:{hx}" aria-hidden="true"></span>'


def frame(s):
    rows = "".join(
        f'<li title="{ROLE_LABEL.get(role, role)}: real vs. found">{swatch(c["brand"])}<span class="arrow">→</span>{swatch(c["closest"])}'
        f'<b>ΔE {c["delta_e"]}</b></li>'
        for role, c in s["drift"]["colors"].items()
    )
    return f"""
    <figure class="frame">
      <img src="{s['web']}" alt="Round {s['round']} post" loading="lazy" width="900" height="900">
      <figcaption>
        <p class="round">Round {s['round']}<span>ΔE {s['drift']['mean_delta_e']}</span></p>
        <ul class="drift">{rows}</ul>
        <p class="font">Font heard as: {esc(short_font(s['heard'].get('font_guess', 'not named')))}</p>
        <details><summary>What the next round heard</summary><p>{esc(s['heard']['description'])}</p></details>
      </figcaption>
    </figure>"""


def chart(runs):
    W, H, L, R, T, B = 640, 300, 44, 40, 16, 40
    rounds = len(runs[0])
    ymax = max(10, max(s["drift"]["mean_delta_e"] for steps in runs for s in steps))
    ymax = int(-(-ymax // 5) * 5)
    x = lambda r: L + (r - 1) * (W - L - R) / max(rounds - 1, 1)
    y = lambda v: T + (1 - v / ymax) * (H - T - B)
    grid = "".join(
        f'<line x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
        f'<text x="{L-8}" y="{y(v)+4:.1f}" text-anchor="end" class="tick">{v}</text>'
        for v in range(0, ymax + 1, 5))
    xt = "".join(f'<text x="{x(r):.1f}" y="{H-B+20}" text-anchor="middle" class="tick">Round {r}</text>'
                 for r in range(1, rounds + 1))
    band = (f'<rect x="{L}" y="{y(2):.1f}" width="{W-L-R}" height="{y(0)-y(2):.1f}" class="band"/>'
            f'<text x="{W-R-6}" y="{y(2)-6:.1f}" text-anchor="end" class="bandlabel">Below 2, most people can\'t see a difference</text>')
    lines = ""
    for i, steps in enumerate(runs):
        col = LINE_COLORS[i % len(LINE_COLORS)]
        pts = [(x(s["round"]), y(s["drift"]["mean_delta_e"]), s) for s in steps]
        lines += f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b, _ in pts)}"/>'
        for a, b, s in pts:
            lines += (f'<circle cx="{a:.1f}" cy="{b:.1f}" r="5" fill="{col}" stroke="var(--paper)" stroke-width="2">'
                      f'<title>Run {i+1}, round {s["round"]}: mean ΔE {s["drift"]["mean_delta_e"]}</title></circle>')
        lx, ly, _ = pts[-1]
        lines += f'<text x="{lx-8:.1f}" y="{ly-12:.1f}" text-anchor="end" class="direct">Run {i+1}</text>'
    legend = "".join(f'<span><i style="background:{LINE_COLORS[i % 2]}"></i>Run {i+1}</span>' for i in range(len(runs)))
    head = "".join(f"<th>Round {r}</th>" for r in range(1, rounds + 1))
    body = "".join(f"<tr><th>Run {i+1}</th>" + "".join(f"<td>{s['drift']['mean_delta_e']}</td>" for s in steps) + "</tr>"
                   for i, steps in enumerate(runs))
    return f"""
    <div class="legend">{legend}</div>
    <div class="scroll"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Average color drift by round for each run">{band}{grid}{xt}{lines}</svg></div>
    <details class="table"><summary>See the numbers</summary>
      <table><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table></details>"""


def notes_html():
    p = ROOT / "notes.md"
    if not p.exists():
        return '<p class="todo">Write notes.md with two or three honest sentences on what you saw, then rebuild.</p>'
    return "".join(f"<p>{esc(par.strip())}</p>" for par in p.read_text().split("\n\n") if par.strip())


def build():
    res = json.loads((ROOT / "results.json").read_text())
    b, runs = res["brand"], res["runs"]
    export_images(runs)
    brand_chips = "".join(f'<li>{swatch(hx)}<span>{ROLE_LABEL.get(k, k)}</span><code>{hx.upper()}</code></li>'
                          for k, hx in b["colors"].items())
    strips = "".join(f'<section class="run"><h3>Run {n}</h3><div class="strip">{"".join(frame(s) for s in steps)}</div></section>'
                     for n, steps in enumerate(runs, 1))
    banner = '<p class="mock">Sample data from a test run with stand-in images. Not real results.</p>' if res["mock"] else ""

    page = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Telephone Test</title>
<meta name="description" content="What happens to a website's look when an AI only ever hears it described.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
:root{{--paper:#E7E6DC;--ink:#22262A;--soft:#5E615C;--rule:#C9C7BC;--cord:#2B3FD6;color-scheme:light}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:400 17px/1.6 "Schibsted Grotesk",system-ui,sans-serif}}
a{{color:var(--cord)}} a:focus-visible,summary:focus-visible{{outline:2px solid var(--cord);outline-offset:3px}}
.wrap{{max-width:1040px;margin:0 auto;padding:0 clamp(20px,7vw,96px)}}
.mock{{background:var(--ink);color:var(--paper);margin:0;padding:10px 16px;text-align:center;font-weight:500}}
header.top{{padding:40px 0 0;font-weight:700}} header.top a{{color:var(--ink);text-decoration:none}}
.hero{{padding:72px 0 40px;max-width:720px}}
h1{{font-size:clamp(40px,7vw,80px);line-height:.98;letter-spacing:-.035em;font-weight:800;margin:0 0 28px}}
.hero p{{font-size:19px;max-width:580px;margin:0;color:var(--soft)}}
.card{{display:flex;flex-wrap:wrap;gap:12px 32px;align-items:center;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:18px 0;margin:8px 0 56px}}
.card ul{{display:flex;flex-wrap:wrap;gap:8px 24px;list-style:none;margin:0;padding:0}}
.card li{{display:flex;align-items:center;gap:8px}} .card code{{font:inherit;color:var(--soft)}}
.chip{{flex-shrink:0;display:inline-block;width:22px;height:22px;border-radius:50%;border:1px solid rgba(34,38,42,.25)}}
h2{{font-size:30px;letter-spacing:-.02em;line-height:1.1;margin:0 0 12px}}
h3{{font-size:18px;margin:0 0 14px}}
.lede{{color:var(--soft);max-width:580px;margin:0 0 28px}}
.run{{margin-bottom:40px}}
.strip{{position:relative;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(140px,1fr);gap:14px;overflow-x:auto;padding-bottom:12px;scroll-snap-type:x mandatory}}
.strip::before{{content:"";position:absolute;left:0;right:0;top:100px;border-top:2px dashed var(--cord);z-index:0}}
.frame{{margin:0;position:relative;z-index:1;scroll-snap-align:start}}
.frame img{{width:100%;height:auto;display:block;border-radius:6px;background:#fff;box-shadow:0 0 0 1px var(--rule)}}
.round{{display:flex;justify-content:space-between;font-weight:700;margin:12px 0 6px}} .round span{{font-weight:500;color:var(--soft)}}
.drift{{list-style:none;padding:0;margin:0 0 8px;font-size:14px}}
.drift li{{display:flex;align-items:center;gap:6px;padding:3px 0}} .drift li .chip{{width:16px;height:16px}}
.drift .arrow{{color:var(--soft);font-size:12px}} .drift b{{font-weight:500;margin-left:auto;white-space:nowrap}}
.font{{font-size:14px;margin:0 0 6px;color:var(--soft)}}
details summary{{cursor:pointer;font-size:14px;color:var(--cord)}} details p{{font-size:14px;color:var(--soft)}}
.chart{{margin:72px 0 0;max-width:660px}} .scroll{{overflow-x:auto}} @media (max-width:640px){{.scroll svg{{min-width:560px}}}} svg{{width:100%;height:auto;display:block}}
.grid{{stroke:var(--rule);stroke-width:1}} .tick{{fill:var(--soft);font-size:12px}}
.band{{fill:var(--ink);opacity:.06}} .bandlabel{{fill:var(--soft);font-size:12px}} .direct{{fill:var(--ink);font-size:13px;font-weight:700}}
.legend{{display:flex;gap:20px;font-size:15px;margin-bottom:8px}} .legend i{{display:inline-block;width:16px;height:3px;vertical-align:middle;margin-right:6px}}
table{{border-collapse:collapse;font-size:15px;margin-top:8px}} th,td{{padding:4px 12px;text-align:right;border-bottom:1px solid var(--rule)}}
.notes{{margin:72px 0 0;max-width:620px}} .notes p{{font-size:18px}} .todo{{color:#B5462E}}
.method{{margin:72px 0 0;max-width:620px;color:var(--soft);font-size:16px}}
footer{{margin:72px 0 0;padding:24px 0 48px;border-top:1px solid var(--rule);font-size:15px;color:var(--soft)}}
@media (max-width:640px){{.hero{{padding:48px 0 32px}} .strip{{grid-auto-columns:78%}} .strip::before{{top:38%}}}}
@media (prefers-reduced-motion:reduce){{.strip{{scroll-behavior:auto}}}}
</style></head>
<body>
{banner}
<div class="wrap">
<header class="top"><a href="https://tonishqakaplish.com">Tonishqa Kaplish</a></header>

<section class="hero">
  <h1>I played telephone with my website.</h1>
  <p>Round one got everything: exact hex codes, the font name, the wordmark. After that, one AI described each post,
  and another made the next post from that description alone. Five rounds, {['once','twice','three times'][min(len(runs),3)-1]}.</p>
</section>

<div class="card"><strong>The original: {esc(b['name'])}</strong><ul>{brand_chips}<li><span>Font</span><code>{esc(b['font'])}</code></li></ul></div>

<h2>Down the line</h2>
<p class="lede">Under each post: background, accent and text, the real color next to what showed up, and ΔE, a score for
how different two colors look. Under 2 is invisible to most people. Over 10 is a different color.</p>
{strips}

<section class="chart">
  <h2>How far the colors moved</h2>
  <p class="lede">Average ΔE across the three colors, round by round.</p>
  {chart(runs)}
</section>

<section class="notes"><h2>What I noticed</h2>{notes_html()}</section>

<section class="method"><h2>How it was made</h2>
<p>Images by {esc(res['image_model'])}, descriptions by {esc(res['vision_model'])}. For each post I pulled the colors that
cover at least half a percent of the image and matched each real color to its closest one, using CIEDE2000 for ΔE.
Fonts are as named by the describing model, so treat them as what it heard, not ground truth.
Two runs is a small sample; this is a quick experiment, not a study.</p></section>

<footer>Built in an evening by Tonishqa Kaplish. <a href="https://tonishqakaplish.com">tonishqakaplish.com</a></footer>
</div></body></html>"""
    (SITE / "index.html").write_text(page)
    print(f"Built {SITE / 'index.html'}")


if __name__ == "__main__":
    build()
