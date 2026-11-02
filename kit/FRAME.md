# Frame, language and transparency

Every quick skill (`/graph`, `/minimalistic-graphics`, `/map-route`, `/breakdown`) takes these spec fields on top of its own.
They are handled by `kit/anim.py`, so a new skill gets them for free as long as its template follows the rules at the end.

| Field | Values | Default | What it does |
|---|---|---|---|
| `format` | `"9:16"` `"16:9"` `"1:1"` `"4:5"` | `"9:16"` | Frame shape: 1080x1920, 1920x1080, 1080x1080, 1080x1350. |
| `lang` | `"en"` `"ru"` `"he"` | guessed from the text | Language of the text. Hebrew lays out right to left. Sets the number format (`34,000` / `34 000`) and the template's own words ("min", "Arrived"). |
| `alpha` | `true` / `"mov"` / `"webm"` | off | Transparent background. `true` = ProRes 4444 `.mov` for an editor (Premiere, Resolve, After Effects); `"webm"` = VP9 with alpha for the web. Not for `/map-route` (the city is the background). |
| `safe` | `"instagram"` `"social"` `"broadcast"` `"none"` | `instagram` for 9:16, `broadcast` otherwise | The red box on the contact sheet. `social` is a conservative union of Reels, TikTok and Shorts (approximate). `broadcast` is a 5% title-safe margin. |
| `rtl` | `true` / `false` | follows `lang` | Force the text direction. |

## Choosing them from the task
- **Where is it going?** A reel, story, TikTok or Short: `9:16`. An insert for a film, a YouTube video or a presentation: `16:9`. A feed post: `4:5` (or `1:1`).
- **Will an editor lay it over footage?** Add `"alpha": true` and hand over the `.mov`. The contact sheet shows it over grey.
- **Which language?** Write the spec's text in the language the user wants. The skill never translates. If the user mixes languages, set `lang` to the one the viewer reads.

## Fonts
Templates keep their Latin fonts. Hebrew glyphs come from Heebo and Cyrillic from Inter / Inter Tight / JetBrains Mono / Montserrat, attached to the same font families with `unicode-range`, so the weights match. Files are in `kit/fonts/intl/` (SIL Open Font License).

## Writing a template that supports all of this
- Size the page with `__W__` and `__H__` (`html`, `body`, `#root`, `data-width`, `data-height`, any full-frame `svg` or `canvas`).
- Read `window.FRAME` = `{format, w, h, alpha, lang, locale, rtl, safe: {l, t, r, b}}` and lay out per format. The simplest way is a small `LAYOUTS` table keyed by format (see `skills/graph/template.html`), or a scaled stage group (see `skills/minimalistic-graphics/template.html`).
- Paint the background on `html`, `body` or `#root`: with `alpha` the kit makes those transparent.
- Use `FRAME.locale` for numbers (`x.toLocaleString(FRAME.locale)`) and keep any words the template writes itself in a per-language table that `SPEC.words` can override (see `skills/map-route/template.html`).
- For right-to-left text, anchor text blocks to the right edge when `FRAME.rtl` is true, and add `unicode-bidi: plaintext` to text that mixes numbers and words.
- Check every format with `--snap` before calling it done.
