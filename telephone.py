"""The Telephone Test: how far does a brand drift when an AI only hears it described?

Round 1 gets the full brand card (hex codes, font name, wordmark) in the prompt.
After that, a vision model describes each post and the image model only ever
sees that description. Like the party game, the message is passed down the line.

Usage:
    python telephone.py                 # real run (needs OPENAI_API_KEY, ANTHROPIC_API_KEY)
    python telephone.py --mock          # fake images, tests the pipeline for free
    python telephone.py --brand brand.example.json
"""
import argparse, base64, json, os, pathlib, random, re

import numpy as np
from PIL import Image, ImageDraw
from skimage.color import rgb2lab, deltaE_ciede2000

ROOT = pathlib.Path(__file__).parent
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1")
VISION_MODEL = os.getenv("VISION_MODEL", "claude-sonnet-5-5")

DESCRIBE = """You are looking at a social media post. Describe it so a designer who has never
seen it could recreate it exactly: the layout, every piece of text word for word, the typeface
(name the font if you can, otherwise describe it), every color as a hex code, the logo or
wordmark, and the background.
Reply with JSON only, no other text:
{"description": "...", "font_guess": "...", "hex_guesses": ["#rrggbb", "..."]}"""


# ---------- the brand card ----------

def load_brand(path):
    brand = json.loads(pathlib.Path(path).read_text())
    fields = {k: v for k, v in brand.items() if k != "colors"} | brand["colors"]
    blanks = [k for k, v in fields.items() if "REPLACE_ME" in str(v)]
    if blanks:
        raise SystemExit(f"Fill in {', '.join(blanks)} in {path} first (or try --brand brand.example.json).")
    return brand


def first_prompt(b):
    c = b["colors"]
    return (
        f"{b['post']} for the brand {b['name']}. "
        f"Use exactly these brand colors: background {c['background']}, accent {c['accent']}, text {c['text']}. "
        f"Set all text in the font {b['font']}. "
        f"Include the brand's wordmark: {b['wordmark']}. "
        f"Headline: \"{b['headline']}\". Tagline: \"{b['tagline']}\". "
        "Clean, premium, on-brand."
    )


# ---------- the two models ----------

def generate_image(prompt, out):
    from openai import OpenAI
    resp = OpenAI().images.generate(model=IMAGE_MODEL, prompt=prompt, size="1024x1024")
    out.write_bytes(base64.b64decode(resp.data[0].b64_json))


def describe_image(path):
    import anthropic
    data = base64.standard_b64encode(path.read_bytes()).decode()
    msg = anthropic.Anthropic().messages.create(
        model=VISION_MODEL, max_tokens=1500,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
            {"type": "text", "text": DESCRIBE},
        ]}],
    )
    text = msg.content[0].text
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0))


# ---------- mock versions, for testing the pipeline without API calls ----------

def mock_generate(prompt, out, brand, round_no, seed):
    rng = random.Random(seed * 100 + round_no)
    def drift(hx):
        rgb = [int(hx[i:i + 2], 16) for i in (1, 3, 5)]
        return tuple(max(0, min(255, v + rng.randint(-6, 6) * round_no)) for v in rgb)
    c = brand["colors"]
    img = Image.new("RGB", (1024, 1024), drift(c["background"]))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 640, 944, 900], fill=drift(c["accent"]))
    d.rectangle([80, 120, 700, 260], fill=drift(c["text"]))
    img.save(out)


def mock_describe(path, brand, round_no):
    return {
        "description": f"[mock round {round_no}] A square post with a light background, a dark title block "
                       "near the top and a colored band along the bottom.",
        "font_guess": ["the brand font", "a geometric sans", "something like Futura", "a rounded sans", "Helvetica"][min(round_no - 1, 4)],
        "hex_guesses": list(brand["colors"].values()),
    }


# ---------- measuring drift ----------

def hex_to_lab(hx):
    rgb = np.array([[[int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]]])
    return rgb2lab(rgb)[0, 0]


def delta_e(hex_a, hex_b):
    """CIEDE2000: how different two colors look to a person. Under ~2, most people can't tell."""
    return float(deltaE_ciede2000(hex_to_lab(hex_a), hex_to_lab(hex_b)))


def main_colors(path, n=12, min_share=0.005):
    """The colors that actually cover the image, biggest first."""
    img = Image.open(path).convert("RGB").resize((256, 256))
    q = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    total = 256 * 256
    out = []
    for count, idx in sorted(q.getcolors(), reverse=True):
        if count / total >= min_share:
            r, g, b = pal[idx * 3: idx * 3 + 3]
            out.append({"hex": f"#{r:02X}{g:02X}{b:02X}", "share": round(count / total, 3)})
    return out


def measure(image_path, brand):
    found = main_colors(image_path)
    per_color = {}
    for role, hx in brand["colors"].items():
        best = min(found, key=lambda f: delta_e(hx, f["hex"]))
        per_color[role] = {"brand": hx.upper(), "closest": best["hex"], "delta_e": round(delta_e(hx, best["hex"]), 1)}
    mean = round(sum(v["delta_e"] for v in per_color.values()) / len(per_color), 1)
    return {"colors": per_color, "mean_delta_e": mean, "main_colors": found[:6]}


# ---------- the chain ----------

def run_chain(brand, run_no, rounds, mock):
    folder = ROOT / "runs" / f"run{run_no}"
    folder.mkdir(parents=True, exist_ok=True)
    prompt = first_prompt(brand)
    steps = []
    for r in range(1, rounds + 1):
        img = folder / f"round{r}.png"
        print(f"run {run_no}, round {r}: generating")
        (mock_generate(prompt, img, brand, r, run_no) if mock else generate_image(prompt, img))
        print(f"run {run_no}, round {r}: describing")
        heard = mock_describe(img, brand, r) if mock else describe_image(img)
        steps.append({"round": r, "image": str(img.relative_to(ROOT)), "prompt": prompt,
                      "heard": heard, "drift": measure(img, brand)})
        prompt = "Create this social media post exactly as described: " + heard["description"]
        (folder / "chain.json").write_text(json.dumps(steps, indent=2))  # save as we go
    return steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", default="brand.json")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()

    brand = load_brand(ROOT / a.brand)
    runs = [run_chain(brand, n, a.rounds, a.mock) for n in range(1, a.runs + 1)]
    results = {"brand": brand, "mock": a.mock, "image_model": "mock" if a.mock else IMAGE_MODEL,
               "vision_model": "mock" if a.mock else VISION_MODEL, "runs": runs}
    (ROOT / "results.json").write_text(json.dumps(results, indent=2))
    for n, steps in enumerate(runs, 1):
        print(f"run {n} mean Delta E by round:", [s["drift"]["mean_delta_e"] for s in steps])
    print("Saved results.json. Next: write notes.md, then python build_page.py")


if __name__ == "__main__":
    main()
