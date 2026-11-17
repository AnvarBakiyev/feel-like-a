"""Builds web/play.html: the page of extella.dev/traffic as one file that opens from disk.
Browsers do not load module files from file://, so traffic_core.js, app.js and palette.css are put inline.
Three.js still comes from a CDN, so the 3D city needs a network connection. "Confirm on the server" and "Best mayors"
call the extella.dev server and show an error when the page is opened from disk; the game itself runs in the page.
python3 web/build_play.py
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    return open(os.path.join(HERE, name), encoding="utf-8").read()


def build():
    core = re.sub(r"^export ", "", read("traffic_core.js"), flags=re.M)
    app = read("app.js")
    imp = re.search(r'^import \{[^}]*\} from "\./traffic_core\.js";\n', app, re.M)
    assert imp, "app.js no longer imports traffic_core.js the expected way"
    app = app[:imp.start()] + app[imp.end():]
    head_imports = "".join(re.findall(r"^import .*\n", app, re.M))
    app = re.sub(r"^import .*\n", "", app, flags=re.M)
    page = read("index.html")
    page = re.sub(r'<link rel="stylesheet" href="palette\.css[^"]*">', lambda m: "<style>\n" + read("palette.css") + "\n</style>", page)
    page = re.sub(r'<link rel="(?:icon|apple-touch-icon)"[^>]*>', "", page)
    page = page.replace('href="/"', 'href="https://extella.dev/"')  # the logo link: the site root, not the disk root
    assert '<script type="module" src="app.js"></script>' in page
    script = "<script type=\"module\">\n" + head_imports + "// ---- traffic_core.js\n" + core + "\n// ---- app.js\n" + app + "</script>"
    page = page.replace('<script type="module" src="app.js"></script>', script)
    return page


if __name__ == "__main__":
    out = build()
    assert "</script>" not in out.split('<script type="module">\n', 1)[1].rsplit("</script>", 1)[0], "a script contains </script>"
    open(os.path.join(HERE, "play.html"), "w", encoding="utf-8").write(out)
    print("web/play.html", len(out), "bytes")
