"""site/ dosyalarından tek sayfalık deneme sürümü üretir (Claude Artifact önizlemesi için).

Kullanım: python3 tools/build_preview.py site /tmp/m4-kasa.html
"""
import json, re, sys, pathlib

site = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])

calc = (site / 'calc.js').read_text()
calc = re.sub(r'^export ', '', calc, flags=re.M)
calc += '\n' + re.sub(r'^export ', '', (site / 'barcode.js').read_text(), flags=re.M)

app = (site / 'app.js').read_text()
app = re.sub(r"^import \{[^}]*\} from '\./[a-z]+\.js';\n", '', app, flags=re.M)
# Veri dosyaları sayfaya gömülür
data = {f'data/{n}.json': json.loads((site / 'data' / f'{n}.json').read_text())
        for n in ('kurallar', 'kampanyalar', 'ifadeler', 'barkodlar')}
app = re.sub(r"async function loadJson\(path\) \{.*?\n\}\n",
             "async function loadJson(path) { return PREVIEW_DATA[path] ?? null; }\n", app, flags=re.S)
# Önizlemede service worker ve yazdırma yok
app = re.sub(r"if \('serviceWorker' in navigator\) \{.*?\n\}\n", '', app, flags=re.S)
assert 'PREVIEW_DATA' in app and 'serviceWorker' not in app and 'import ' not in app

css = (site / 'app.css').read_text()
# Tema: koyu öncelikli; açık tema sistem tercihiyle veya data-theme ile
light = """--bg: #f5f5f5; --surface: #fff; --surface-2: #ececec; --text: #141414;
    --muted: #666; --line: #dcdcdc; --ok: #0a8a42; --warn: #b36b00; color-scheme: light;"""
css = re.sub(r"@media \(prefers-color-scheme: light\) \{\n  :root \{.*?\n  \}\n\}\n",
             "@media (prefers-color-scheme: light) {\n  :root:not([data-theme=\"dark\"]) { " + light + " }\n}\n"
             ":root[data-theme=\"light\"] { " + light + " }\n", css, flags=re.S)
css = css.replace("""  position: sticky; top: 0; z-index: 5;""",
                  """  position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5;""")
css = css.replace("""  padding: calc(8px + env(safe-area-inset-top)) 16px 8px;""",
                  """  padding-block: 8px;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));""")
css = css.replace("""main { padding: 12px 16px; max-width: 640px; margin: 0 auto; }""",
                  """main {
  padding-block: 12px;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  max-width: 640px; margin: 0 auto;
}
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--bg); }
.preview-note { font-size: 13px; color: var(--muted); border: 1px dashed var(--line); border-radius: var(--radius); padding: 8px 12px; margin-bottom: 4px; }""")
css += "\n@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }\n"

html = (site / 'index.html').read_text()
body = re.search(r'<body>\n(.*)</body>', html, flags=re.S).group(1)
# Yazdırma bu ortamda çalışmaz: Kasa kartı bölümünü kaldır
# Yazdırma bu ortamda çalışmaz: Kasa kartı (⚙) butonunu gizle
body = re.sub(r'\s*<button id="openSettings".*?</button>', '', body, flags=re.S)
assert 'id="openSettings"' not in body
body = body.replace('<main>', '<main>\n    <p class="preview-note">Deneme sürümü. Girdiğin kurlar yalnızca bu tarayıcıda saklanır.</p>', 1)
# printCard dinleyicisi elemanı arar; yoksa atla
app = app.replace("$('openSettings').addEventListener(", "$('openSettings')?.addEventListener(")

page = f"""<title>M4 Kasa</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
{css}
</style>
{body}
<script>
(() => {{
const PREVIEW_DATA = {json.dumps(data, ensure_ascii=False)};
{calc}
{app}
}})();
</script>
"""
out.write_text(page)
print(out, len(page))
