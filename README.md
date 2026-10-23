# The Telephone Test

What happens to a brand when an AI only ever hears it described?

Round 1 gets the whole brand card in the prompt: exact hex codes, the font name, the wordmark. After that, a vision model describes each post, and the image model makes the next post from that description alone. Five rounds, twice. Each round measures how far the brand colors moved using ΔE (CIEDE2000), a standard score for how different two colors look to a person. Under 2 is invisible to most people; over 10 is a different color.

Two scripts, no framework:

- `telephone.py` runs the chain and measures the drift, saving `results.json`
- `build_page.py` turns the results into a static page in `site/`

## See the Results: https://telephone-test-seven.vercel.app

Two runs, five rounds each. Brand colors: background `#E7E6DC`, accent `#E6B04A`, text `#2D322F`. Font: Bricolage Grotesque.

ΔE scores how different two colors look to a person. Under 2, most people can't tell. Over 10, it's a different color.

| Run | Round | Background ΔE | Accent ΔE | Text ΔE | Average | Font the AI named first |
|---|---|---|---|---|---|---|
| 1 | 1 | 2.2 | 7.3 | 8.2 | 5.9 | DM Sans |
| 1 | 2 | 3.6 | 4.6 | 16.1 | 8.1 | Inter |
| 1 | 3 | 4.9 | 2.5 | 13.2 | 6.9 | Bricolage Grotesque |
| 1 | 4 | 6.1 | 3.7 | 11.6 | 7.1 | Plus Jakarta Sans |
| 1 | 5 | 4.0 | 10.7 | 15.5 | 10.1 | Plus Jakarta Sans |
| 2 | 1 | 2.2 | 23.8* | 30.9 | 19.0 | Cabinet Grotesk |
| 2 | 2 | 4.6 | 8.1 | 16.1 | 9.6 | Plus Jakarta Sans |
| 2 | 3 | 3.6 | 8.1 | 12.4 | 8.0 | Instrument Sans |
| 2 | 4 | 5.0 | 5.9 | 13.5 | 8.1 | Inter Display |
| 2 | 5 | 3.8 | 2.6 | 13.8 | 6.7 | Graphik |

\* By eye, the yellow in this round is close to the brand. It likely covered too small an area for the color measurement to catch, so it was matched against a different color.

### What I saw by eye

| Comparison | What changed |
|---|---|
| My site vs. run 1, round 1 | Yellow matched. Charcoal text became plain black. Font turned generic. Name spelled right. |
| Run 1, round 1 vs. round 5 | Layout and spelling held. Yellow shifted to a worse shade. Colors got bolder. |
| My site vs. run 2, round 1 | Layout, text color and font were all off. Yellow was fairly close. |
| Run 2, round 1 vs. round 5 | Looked worse by round 5 and put things in the wrong order, even though the color scores improved. |
| Run 1 vs. run 2, final rounds | One kept the layout, the other chased the color. Neither ever got the font right. |

### Takeaways

1. Exact color codes in the prompt didn't hold. The text color was off from the very first round.
2. The font never came back. Bricolage was named once in ten rounds; otherwise the AI reached for Inter, Plus Jakarta Sans and DM Sans.
3. Color scores and what the post looked like didn't always agree. A number only measures what you point it at.

## Run it

1. **Install.**
   ```
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Add your API keys.**
   ```
   export OPENAI_API_KEY=sk-...
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
   If OpenAI asks you to verify your organization before using the image model, do that in the OpenAI dashboard first.

3. **Fill in `brand.json`.** Three fields say `REPLACE_ME`: your font and two hex colors. To find them on your site, open it in Chrome, right-click the wordmark, choose Inspect, and look under Computed for `font-family` and `color`. Prefer a made-up brand? Use `--brand brand.example.json`.

4. **Optional free dry run.** `python telephone.py --mock && python build_page.py` makes stand-in images so you can preview the page. Delete `runs/`, `results.json` and `site/` afterwards.

5. **Run it for real.** `python telephone.py` makes 10 images and 10 descriptions. Expect roughly 5 to 10 minutes and a couple of dollars. Results save as they go, so a crash mid-run doesn't lose earlier rounds.

6. **Look before you write.** Open the images in `runs/`. Write `notes.md` with two or three honest sentences on what you saw: where the font turned into a lookalike, which color slipped first, anything that surprised you. If the drift was smaller than expected, say that.

7. **Build the page.** `python build_page.py` writes `site/index.html` and resized images.

8. **Deploy.** `npx vercel site --prod`, or drag the `site` folder into vercel.com.

## Settings

- `--rounds 5 --runs 2` are the defaults.
- `IMAGE_MODEL` (default `gpt-image-1`) and `VISION_MODEL` (default `claude-sonnet-5-5`) can be swapped with environment variables.

## Limits, stated plainly

- Color matching finds the closest color covering at least 0.5% of the image, so a brand color can "match" something elsewhere in the post.
- Fonts are as named by the describing model: what it heard, not ground truth.
- Two runs is a small sample. This is a quick experiment, not a study.