#!/usr/bin/env python3
"""Shared helpers for the animation skills. Standard library only (plus ffmpeg and npx on the PATH).

A builder fills a skill's template.html with its spec and renders it with HyperFrames:
    anim.build(template, defaults, duration=lambda spec: 4.0, three=False)

Every quick skill also understands these spec fields (handled here, not in the skill):
    "format": "9:16" | "16:9" | "1:1" | "4:5"     frame shape (default 9:16, 1080x1920)
    "alpha":  false | true | "mov" | "webm"         transparent background; true means ProRes 4444 .mov
    "safe":   "instagram" | "social" | "broadcast" | "none"   the box drawn on the contact sheet
    "lang":   "en" | "ru" | "he"                     language of the text; guessed from the spec's text when left out.
                                                    Sets direction (he is right-to-left), number format and template words
    "rtl":    true | false                          force the direction; normally follows "lang"

Templates read the frame as window.FRAME = {format, w, h, alpha, lang, locale, rtl, safe: {l, t, r, b}} and use
__W__ / __H__.
Hebrew (Heebo) and Cyrillic glyphs are added to the templates' own font families with unicode-range, so a
template written for Latin text renders Hebrew and Russian without changes.

From the command line:
    python3 kit/anim.py sheet <video> <out.jpg> [n] [format] [safe]   # contact sheet with the safe area in red
    python3 kit/anim.py still <video> <t> <out.jpg>                   # one frame
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
HYPERFRAMES = 'hyperframes@0.8.34'
FPS = 30
W, H = 1080, 1920                                         # the default frame; kept for older callers

FORMATS = {'9:16': (1080, 1920), '16:9': (1920, 1080), '1:1': (1080, 1080), '4:5': (1080, 1350)}
KIT_FIELDS = {'out', 'hold', 'template', 'format', 'alpha', 'safe', 'rtl', 'lang'}
HEBREW_CHARS = re.compile('[\u0590-\u05FF\uFB1D-\uFB4F]')
CYRILLIC_CHARS = re.compile('[\u0400-\u04FF]')
LANGS = {'en': 'en-US', 'ru': 'ru-RU', 'he': 'he-IL'}


def safe_box(fmt, profile):
    """margins (left, top, right, bottom) in px that the platform's UI or a TV may cover"""
    w, h = FORMATS[fmt]
    if profile == 'none':
        return (0, 0, 0, 0)
    if profile == 'instagram' and fmt == '9:16':
        return (100, 220, 100, 420)                       # Reels: top bar, caption + buttons at the bottom
    if profile == 'social' and fmt == '9:16':
        return (80, 250, 170, 480)                        # a conservative union of Reels, TikTok and Shorts (approximate)
    # broadcast title-safe (90%), also a sensible margin for feed posts and film inserts
    mx, my = round(w * .05), round(h * .05)
    return (mx, my, mx, my)


def default_safe(fmt):
    return 'instagram' if fmt == '9:16' else 'broadcast'


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def duration(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(video)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def video_size(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                        '-of', 'csv=p=0', str(video)], capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split(',')[:2]
    return int(w), int(h)


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy(src, dst)


def check_setup(three):
    missing = []
    if not (KIT / 'vendor' / 'gsap.min.js').exists():
        missing.append('GSAP')
    if three and not (KIT / 'node_modules' / 'three' / 'build' / 'three.module.js').exists():
        missing.append('three.js')
    if missing:
        sys.exit(f'{" and ".join(missing)} not found: run  bash "{KIT}/setup.sh"  once, then build again')


def load_spec(path, defaults):
    spec = json.loads(Path(path).read_text())
    for k, v in defaults.items():
        spec.setdefault(k, v)
    unknown = sorted(set(spec) - set(defaults) - KIT_FIELDS)
    if unknown:
        print(f'note: ignoring unknown spec fields: {", ".join(unknown)}')
    return spec


def guess_lang(spec):
    """the language of the spec's text: Hebrew wins over Cyrillic, Cyrillic over Latin"""
    text = json.dumps({k: v for k, v in spec.items() if k not in KIT_FIELDS}, ensure_ascii=False)
    if HEBREW_CHARS.search(text):
        return 'he'
    if CYRILLIC_CHARS.search(text):
        return 'ru'
    return 'en'


def frame_of(spec, formats=None):
    """the frame a spec asks for, checked against the formats the skill supports"""
    fmt = str(spec.get('format') or '9:16')
    allowed = formats or list(FORMATS)
    if fmt not in FORMATS or fmt not in allowed:
        sys.exit(f'spec: "format" must be one of {", ".join(allowed)} (got "{fmt}")')
    alpha = spec.get('alpha') or False
    if alpha is True:
        alpha = 'mov'
    if alpha not in (False, 'mov', 'webm'):
        sys.exit('spec: "alpha" is true, "mov" or "webm"')
    profile = spec.get('safe') or default_safe(fmt)
    if profile not in ('instagram', 'social', 'broadcast', 'none'):
        sys.exit('spec: "safe" is "instagram", "social", "broadcast" or "none"')
    lang = spec.get('lang') or guess_lang(spec)
    if lang not in LANGS:
        sys.exit(f'spec: "lang" is one of {", ".join(LANGS)}')
    rtl = spec.get('rtl')
    if rtl is None:
        rtl = lang == 'he'
    w, h = FORMATS[fmt]
    l, t, r, b = safe_box(fmt, profile)
    return {'format': fmt, 'w': w, 'h': h, 'alpha': alpha, 'rtl': bool(rtl), 'profile': profile,
            'lang': lang, 'locale': LANGS[lang],
            'safe': {'l': l, 't': t, 'r': r, 'b': b}}


# Hebrew and Cyrillic faces stacked onto the families the templates already use. Faces declared later win for the
# characters in their unicode-range, so Latin keeps the template's own font.
HEBREW = 'U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F'
CYRILLIC = 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116'
INTL = {  # family: [(weight, hebrew file, cyrillic file)]
    'Inter': [(400, 'heebo-hebrew-400', 'inter-cyrillic-400'), (500, 'heebo-hebrew-500', 'inter-cyrillic-500'),
              (600, 'heebo-hebrew-600', 'inter-cyrillic-600'), (700, 'heebo-hebrew-700', 'inter-cyrillic-700'),
              (800, 'heebo-hebrew-800', 'inter-cyrillic-700')],
    'Inter Tight': [(700, 'heebo-hebrew-800', 'inter-tight-cyrillic-700'),
                    (800, 'heebo-hebrew-800', 'inter-tight-cyrillic-700')],
    'Poppins': [(400, 'heebo-hebrew-400', 'montserrat-cyrillic-400'), (700, 'heebo-hebrew-700', 'inter-cyrillic-700')],
    'JB': [(500, 'heebo-hebrew-500', 'jetbrains-mono-cyrillic-500')],
    'Lora': [(400, 'heebo-hebrew-400', 'inter-cyrillic-400')],
}


def intl_css():
    out = []
    for fam, faces in INTL.items():
        for w, he, cy in faces:
            out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url(fonts/intl/{cy}-normal.woff2) "
                       f"format('woff2');unicode-range:{CYRILLIC}}}")
            out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url(fonts/intl/{he}-normal.woff2) "
                       f"format('woff2');unicode-range:{HEBREW}}}")
    return '\n'.join(out)


def head_inject(frame):
    """window.FRAME, the alpha background and the extra fonts, placed at the end of <head>"""
    cls = ' '.join(c for c, on in (('alpha', frame['alpha']), ('rtl', frame['rtl']), (f"f{frame['w']}x{frame['h']}", 1)) if on)
    data = {k: frame[k] for k in ('format', 'w', 'h', 'alpha', 'lang', 'locale', 'rtl', 'safe')}
    js = (f'<script>window.FRAME={json.dumps(data)};'
          f'document.documentElement.className+=" {cls}";'
          + f'document.documentElement.lang="{frame["lang"]}";'
          + ('document.documentElement.dir="rtl";' if frame['rtl'] else '')
          + '</script>')
    css = intl_css()
    if frame['alpha']:
        css += '\nhtml.alpha,html.alpha body,html.alpha #root{background:transparent!important}'
    return f'{js}\n<style>\n{css}\n</style>\n'


def prepare(template, spec, dur, work, three=False, frame=None):
    """writes the render folder: index.html with the spec filled in, fonts, GSAP and (if needed) three.js"""
    frame = frame or frame_of(spec)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    html = Path(template).read_text()
    data = json.dumps(spec, ensure_ascii=False).replace('</', '<\\/')
    html = (html.replace('__SPEC__', data).replace('__DURATION__', f'{dur:.3f}')
            .replace('__W__', str(frame['w'])).replace('__H__', str(frame['h'])))
    html = html.replace('</head>', head_inject(frame) + '</head>', 1)
    (work / 'index.html').write_text(html)
    for f in (KIT / 'fonts').rglob('*.woff2'):
        link(f, work / 'fonts' / f.relative_to(KIT / 'fonts'))
    link(KIT / 'vendor' / 'gsap.min.js', work / 'vendor' / 'gsap.min.js')
    if three:
        t = KIT / 'node_modules' / 'three'
        link(t / 'build' / 'three.module.js', work / 'vendor' / 'three' / 'three.module.js')
        for rel in ['environments/RoomEnvironment.js']:
            link(t / 'examples' / 'jsm' / rel, work / 'vendor' / 'three' / 'addons' / rel)


def browser_env():
    """on Linux, point HyperFrames at an installed Chrome when it has none of its own"""
    env = dict(os.environ)
    if 'HYPERFRAMES_BROWSER_PATH' not in env and sys.platform.startswith('linux'):
        for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
            p = shutil.which(name)
            if p:
                env['HYPERFRAMES_BROWSER_PATH'] = p
                break
    return env


def hyperframes(*args):
    return subprocess.run(['npx', '--yes', HYPERFRAMES, *map(str, args)], capture_output=True, text=True,
                          env=browser_env())


def render(work, out, alpha=False):
    out = Path(out)
    if out.exists():
        out.unlink()
    print(f'rendering {out.name} ...', flush=True)
    args = ['render', work, '-o', out, '--fps', FPS]
    args += ['--format', alpha] if alpha else ['-q', 'high']
    r = hyperframes(*args)
    if not out.exists():
        sys.exit(f'render failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    print('\n'.join(l.strip() for l in r.stdout.splitlines() if 'rendered in' in l))


def snapshots(work, times, out_dir):
    """quick PNG frames at the given times, without a full render"""
    r = hyperframes('snapshot', work, '--at', ','.join(f'{t:g}' for t in times))
    shots = sorted((work / 'snapshots').glob('frame-*.png'))
    if not shots:
        sys.exit(f'snapshot failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in shots:
        shutil.copy(f, out_dir / f.name)
    print(f'wrote {len(shots)} snapshots to {out_dir}')


def has_alpha(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=pix_fmt',
                        '-of', 'csv=p=0', str(video)], capture_output=True, text=True)
    pf = r.stdout.strip()
    return pf.startswith(('yuva', 'rgba', 'argb', 'bgra', 'abgr', 'gbra', 'ya'))


def sheet(video, out, n=6, fmt=None, profile=None, alpha=None):
    """contact sheet of a finished video; the red box is what the safe-area profile leaves uncovered.
    Transparent videos are laid over grey so both light and dark artwork shows."""
    if alpha is None:
        alpha = has_alpha(video)
    vw, vh = video_size(video)
    if fmt is None:
        fmt = next((f for f, s in FORMATS.items() if s == (vw, vh)), '9:16')
    profile = profile or default_safe(fmt)
    w, h = FORMATS[fmt]
    l, t, r, b = safe_box(fmt, profile)
    if h >= w:
        th = 480; tw = round(th * w / h); cols, rows = n, 1
    else:
        tw = 480; th = round(tw * h / w); cols, rows = (n + 1) // 2, 2
        n = cols * rows
    k = tw / w
    draw = f'drawbox=x={l * k:.0f}:y={t * k:.0f}:w={(w - l - r) * k:.0f}:h={(h - t - b) * k:.0f}:color=red@0.8:t=2'
    rate = n / duration(video)
    chain = f'fps={rate:.5f},scale={tw}:{th}'
    if alpha:
        fc = (f'color=c=0x7f7f7f:s={tw}x{th}:r={FPS}[bg];[0:v]scale={tw}:{th},format=rgba[fg];'
              f'[bg][fg]overlay=shortest=1,fps={rate:.5f},{draw},tile={cols}x{rows}')
    else:
        fc = f'[0:v]{chain},{draw},tile={cols}x{rows}'
    run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-filter_complex', fc, '-frames:v', '1', out])


def still(video, t, out):
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', video, '-frames:v', '1', out])


def build(template, defaults, duration=lambda spec: 4.0, three=False, check=None, formats=None, alpha_ok=True):
    """the whole builder CLI:  build.py <spec.json> [--snap 1.5,3.2]  ->  <spec>.mp4 (or .mov/.webm) + <spec>.sheet.jpg"""
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        sys.exit(f'usage: {Path(sys.argv[0]).name} <spec.json> [--snap 1.5,3.2]')
    spec_path = Path(args[0]).resolve()
    snap = None
    if '--snap' in args:
        snap = [float(x) for x in args[args.index('--snap') + 1].split(',')]
    check_setup(three)
    spec = load_spec(spec_path, defaults)
    frame = frame_of(spec, formats)
    if frame['alpha'] and not alpha_ok:
        sys.exit('spec: this skill has a full background and does not render with "alpha"')
    if check:
        check(spec)
    dur = duration(spec) + float(spec.get('hold', 0))
    ext = '.' + frame['alpha'] if frame['alpha'] else '.mp4'
    out = Path(spec['out']) if spec.get('out') else spec_path.with_suffix(ext)
    if not out.is_absolute():
        out = spec_path.parent / out
    if frame['alpha'] and out.suffix.lower() not in ('.mov', '.webm'):
        out = out.with_suffix(ext)
    if spec.get('template'):                      # a customised copy of the skill's template, next to the spec
        template = (spec_path.parent / spec['template']).resolve()
    work = spec_path.parent / '.work' / out.stem
    prepare(template, spec, dur, work, three, frame)
    if snap:
        snapshots(work, snap, out.with_suffix('.snaps'))
        return
    render(work, out, frame['alpha'])
    sh = out.with_suffix('.sheet.jpg')
    sheet(out, sh, fmt=frame['format'], profile=frame['profile'])
    print(f'done: {out}\nsheet: {sh}')


def main():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == 'sheet':
        sheet(a[1], a[2], int(a[3]) if len(a) > 3 else 6, a[4] if len(a) > 4 else None, a[5] if len(a) > 5 else None)
        print('wrote', a[2])
    elif len(a) == 4 and a[0] == 'still':
        still(a[1], float(a[2]), a[3])
        print('wrote', a[3])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
