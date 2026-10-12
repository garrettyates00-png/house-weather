"""Procedural, tileable PBR textures for the Yellow House Blender model.

Writes <name>_col.png (sRGB), <name>_nrm.png (OpenGL tangent normal), <name>_rgh.png
into tex/. Every map tiles seamlessly; the tile size in meters is noted per texture
and used by model.py for world-space UVs.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tex")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(968)


def band_noise(n, lo, hi, seed=None, aniso=(1.0, 1.0)):
    """Tileable noise containing spatial frequencies lo..hi (cycles per tile)."""
    r = np.random.default_rng(seed) if seed is not None else rng
    w = r.standard_normal((n, n))
    fy = np.fft.fftfreq(n)[:, None] * n * aniso[1]
    fx = np.fft.fftfreq(n)[None, :] * n * aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    mask = np.exp(-((np.log2(np.maximum(f, 1e-6)) - np.log2((lo * hi) ** 0.5)) ** 2) / (2 * (0.5 * np.log2(hi / lo) + 0.4) ** 2))
    mask[0, 0] = 0
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * mask))
    return (out - out.mean()) / (out.std() + 1e-9)


def fbm(n, base=2, octaves=6, gain=0.55, seed=None, aniso=(1.0, 1.0)):
    out, amp, tot = np.zeros((n, n)), 1.0, 0.0
    for o in range(octaves):
        f = base * 2 ** o
        out += amp * band_noise(n, f * 0.7, f * 1.4, None if seed is None else seed + o, aniso)
        tot += amp
        amp *= gain
    return out / tot


def blur(a, px):
    """Wrap-around gaussian blur (keeps tiling)."""
    n = a.shape[0]
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.fftfreq(a.shape[1])[None, :]
    g = np.exp(-2 * (np.pi * px) ** 2 * (fx * fx + fy * fy))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def normal_from_height(h, meters_per_px, strength=1.0):
    """h in meters, image row 0 = top (v = 1). Returns OpenGL normal map uint8."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * meters_per_px)
    dy_down = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * meters_per_px)
    dy = -dy_down  # +v points up the image
    nx, ny, nz = -dx * strength, -dy * strength, np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], -1)
    return ((n * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255.0


def save(name, col, nrm=None, rgh=None):
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(f"{OUT}/{name}_col.png")
    if nrm is not None:
        Image.fromarray(nrm).save(f"{OUT}/{name}_nrm.png")
    if rgh is not None:
        Image.fromarray((np.clip(rgh, 0, 1) * 255).astype(np.uint8)).save(f"{OUT}/{name}_rgh.png")
    print("wrote", name)


def tint(base, var):
    return np.clip(base[None, None, :] * (1 + var[..., None]), 0, 1)


# ---------------------------------------------------------------- siding
def siding(n=1024, tile=1.44, boards=8, color="#efe2a0"):
    mpp = tile / n
    v = (np.arange(n)[::-1] + 0.5)[:, None] / n * tile  # meters from tile bottom, per row
    v = np.repeat(v, n, 1)
    exp = tile / boards
    t = (v % exp) / exp                       # 0 at a board's butt (bottom), 1 at its top
    h = 0.011 * (1 - t) + 0.003               # thick butt tapering up
    bev = np.clip(t / 0.03, 0, 1)             # small rounded butt edge
    h = h * (0.6 + 0.4 * bev)
    h = blur(h, 1.0)
    grain = fbm(n, 4, 5, seed=11, aniso=(0.12, 1.0))   # long horizontal embossed grain
    h += grain * 0.00025
    shade = np.where(t > 0.86, -0.22 * (np.clip(t - 0.86, 0, None) / 0.14) ** 1.5, 0.0)  # shadow under the next butt
    var = 0.035 * fbm(n, 2, 4, seed=12) + 0.02 * grain + shade
    col = tint(hexrgb(color), var)
    rough = 0.62 + 0.06 * fbm(n, 6, 4, seed=13)
    save("siding", col, normal_from_height(h, mpp), rough)


# ---------------------------------------------------------------- shingles
def shingles(n=1024, tile=1.0, courses=7, color="#727c86"):
    mpp = tile / n
    col = np.zeros((n, n, 3))
    h = np.zeros((n, n))
    base = hexrgb(color)
    yy = (np.arange(n)[::-1] + 0.5)[:, None] / n * tile
    xx = (np.arange(n) + 0.5)[None, :] / n * tile
    YY, XX = np.repeat(yy, n, 1), np.repeat(xx, n, 0)
    exp = tile / courses
    for c in range(courses):
        y0 = c * exp
        rows = (YY >= y0) & (YY < y0 + exp)
        # random tab widths, wrapped so the tile stays seamless
        x0 = rng.uniform(0, tile)
        edges, x = [x0], x0
        while True:
            x += rng.uniform(0.11, 0.33)
            if x > x0 + tile - 0.1:
                break
            edges.append(x)
        edges.append(x0 + tile)
        tabs = [(edges[i] % tile, edges[i] % tile + (edges[i + 1] - edges[i])) for i in range(len(edges) - 1)]
        for a, b in tabs:
            inx = ((XX - a) % tile) < (b - a)
            m = rows & inx
            shade = rng.normal(0, 0.05)
            dark = rng.random() < 0.22  # laminated shadow band near the butt
            local = (YY - y0) / exp
            tabcol = base * (1 + shade)
            col[m] = tabcol
            hh = 0.006 * (1 - local) + 0.002 + rng.uniform(0, 0.0015)
            h[m] = hh[m]
            if dark:
                band = m & (local < rng.uniform(0.25, 0.45))
                col[band] *= 0.84
                h[band] += 0.0015
            gap = m & ((((XX - a) % tile) < 0.004) | (((XX - a) % tile) > (b - a) - 0.002))
            col[gap] *= 0.45
            h[gap] -= 0.004
        butt = rows & (((YY - y0) / exp) < 0.05)
        col[butt] *= 0.88
    gran = band_noise(n, 180, 420, seed=21)
    col *= 1 + 0.2 * gran[..., None]
    col *= 1 + 0.06 * fbm(n, 2, 4, seed=22)[..., None]
    h += 0.0003 * gran
    h = blur(h, 0.6)
    rough = 0.9 + 0.05 * gran
    save("shingle", col, normal_from_height(h, mpp), rough)


# ---------------------------------------------------------------- concrete family
def concrete(name, n=1024, tile=2.0, color="#aaa69c", stains=0.07, speck=0.05, rough_base=0.82, joints=None):
    mpp = tile / n
    big = fbm(n, 1, 4, seed=hash(name) % 1000)
    pores = band_noise(n, 150, 400, seed=hash(name) % 1000 + 5)
    var = stains * big + speck * pores + 0.03 * fbm(n, 8, 3, seed=7)
    col = tint(hexrgb(color), var)
    h = 0.0006 * fbm(n, 6, 4, seed=31) + 0.0002 * pores
    if joints:
        for frac in joints:
            px = int(frac * n)
            col[:, max(px - 2, 0):px + 2] *= 0.55
            h[:, max(px - 2, 0):px + 2] -= 0.004
    rough = rough_base + 0.08 * fbm(n, 3, 4, seed=33)
    save(name, col, normal_from_height(blur(h, 0.7), mpp), rough)


def asphalt(n=1024, tile=3.0):
    mpp = tile / n
    stones = band_noise(n, 250, 500, seed=41)
    col = tint(hexrgb("#3c3e41"), 0.18 * stones + 0.1 * fbm(n, 2, 5, seed=42))
    h = 0.0012 * np.clip(stones, 0, None)
    rough = 0.88 - 0.1 * np.clip(stones, 0, 2) / 2
    save("asphalt", col, normal_from_height(h, mpp), rough)


# ---------------------------------------------------------------- mulch
def mulch(n=1024, tile=1.0):
    mpp = tile / n
    img = Image.new("RGB", (n, n), (52, 32, 21))
    hgt = Image.new("L", (n, n), 0)
    d, dh = ImageDraw.Draw(img), ImageDraw.Draw(hgt)
    for i in range(16000):
        x, y = rng.uniform(0, n), rng.uniform(0, n)
        L, W, a = rng.uniform(10, 34), rng.uniform(3, 8), rng.uniform(0, np.pi)
        tone = rng.uniform(0.55, 1.25)
        c = tuple(int(min(255, v * tone)) for v in (104, 62, 38))
        hv = int(40 + 215 * (i / 16000))
        ca, sa = np.cos(a), np.sin(a)
        pts = [(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)]
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                poly = [(x + ox + px * ca - py * sa, y + oy + px * sa + py * ca) for px, py in pts]
                d.polygon(poly, fill=c)
                dh.polygon(poly, fill=hv)
    col = np.asarray(img, float) / 255
    h = np.asarray(hgt.filter(ImageFilter.GaussianBlur(1.2)), float) / 255 * 0.012
    col *= 1 + 0.08 * band_noise(n, 100, 300, seed=51)[..., None]
    rough = 0.9 + 0.05 * band_noise(n, 50, 200, seed=52)
    save("mulch", col, normal_from_height(h, mpp), rough)


# ---------------------------------------------------------------- wood fence (board-on-board pickets)
def fence(n=1024, tile=1.12, pickets=8):
    mpp = tile / n
    xx = (np.arange(n) + 0.5)[None, :] / n * tile
    XX = np.repeat(xx, n, 0)
    w = tile / pickets
    t = (XX % w) / w
    idx = (XX // w).astype(int)
    grain = fbm(n, 6, 5, seed=61, aniso=(1.0, 0.1))
    knots = np.clip(band_noise(n, 10, 20, seed=62) - 2.2, 0, None)
    shade = np.array([rng.normal(0, 0.08) for _ in range(pickets)])[idx]
    base = hexrgb("#8a7258")
    var = shade + 0.12 * grain - 0.4 * knots
    col = tint(base, var)
    edge = (t < 0.015) | (t > 0.985)
    col[edge] *= 0.35
    h = 0.001 * grain - 0.006 * edge + 0.003 * (np.abs(t - 0.5) < 0.48)
    rough = 0.85 + 0.05 * grain
    save("fence", col, normal_from_height(blur(h, 0.8), mpp), rough)


# ---------------------------------------------------------------- lawn base (under the grass)
def lawn(n=1024, tile=4.0):
    mpp = tile / n
    blades = band_noise(n, 200, 500, seed=71)
    patches = fbm(n, 1, 4, seed=72)
    g = hexrgb("#4f7a2c")
    y = hexrgb("#7c8a3a")
    m = np.clip(0.5 + 0.35 * patches, 0, 1)[..., None]
    col = g[None, None] * (1 - m) + y[None, None] * m
    col *= 1 + 0.22 * blades[..., None]
    rough = 0.92 + 0.03 * blades
    save("lawn", col, normal_from_height(0.002 * blades, mpp), rough)


def pavers(n=1024, tile=0.9, k=3):
    mpp = tile / n
    s = n // k
    col = np.zeros((n, n, 3))
    h = np.zeros((n, n))
    for r in range(k):
        for c in range(k):
            v = 0.56 + rng.uniform(-0.05, 0.05)
            col[r * s:(r + 1) * s, c * s:(c + 1) * s] = (v * 0.97, v, v * 1.02)
            h[r * s + 6:(r + 1) * s - 6, c * s + 6:(c + 1) * s - 6] = 0.008
    col *= 1 + 0.1 * band_noise(n, 80, 300, seed=81)[..., None]
    col[h == 0] *= 0.45
    rough = 0.8 + 0.08 * band_noise(n, 40, 200, seed=82)
    save("paver", col, normal_from_height(blur(h, 2.0), mpp), rough)


# ---------------------------------------------------------------- foliage
def leafy(name, n=1024, tile=0.6, greens=("#2f5a24", "#3f6e2a", "#55833a", "#26461c")):
    """Dense small-leaf surface for clipped shrubs."""
    mpp = tile / n
    img = Image.new("RGB", (n, n), (24, 40, 18))
    hgt = Image.new("L", (n, n), 0)
    d, dh = ImageDraw.Draw(img), ImageDraw.Draw(hgt)
    pal = [tuple(int(c * 255) for c in hexrgb(g)) for g in greens]
    for i in range(9000):
        x, y = rng.uniform(0, n), rng.uniform(0, n)
        r1, r2 = rng.uniform(6, 13), rng.uniform(3, 6)
        c = pal[rng.integers(len(pal))]
        c = tuple(int(min(255, v * rng.uniform(0.75, 1.25))) for v in c)
        hv = int(30 + 225 * i / 9000)
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                bb = [x + ox - r1, y + oy - r2, x + ox + r1, y + oy + r2]
                d.ellipse(bb, fill=c)
                dh.ellipse(bb, fill=hv)
    img = img.rotate(0)
    col = np.asarray(img, float) / 255
    h = np.asarray(hgt.filter(ImageFilter.GaussianBlur(1.5)), float) / 255 * 0.02
    save(name, col, normal_from_height(h, mpp), 0.75 + 0.1 * band_noise(n, 30, 120, seed=91))


def leaf_card(n=512):
    """RGBA cluster of leaves on transparency for tree crowns."""
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pal = [(70, 104, 38), (92, 122, 44), (58, 88, 30), (120, 132, 52), (150, 128, 50)]
    for i in range(140):
        cx, cy = rng.normal(n / 2, n / 6), rng.normal(n / 2, n / 6)
        if not (40 < cx < n - 40 and 40 < cy < n - 40):
            continue
        L, W, a = rng.uniform(28, 46), rng.uniform(13, 20), rng.uniform(0, np.pi * 2)
        c = pal[rng.integers(len(pal))]
        c = tuple(int(min(255, v * rng.uniform(0.8, 1.2))) for v in c) + (255,)
        pts = []
        for k in range(16):
            th = k / 16 * 2 * np.pi
            px, py = L / 2 * np.cos(th), W / 2 * np.sin(th) * (1 - 0.3 * np.cos(th))
            pts.append((cx + px * np.cos(a) - py * np.sin(a), cy + px * np.sin(a) + py * np.cos(a)))
        d.polygon(pts, fill=c)
        d.line([pts[0], pts[8]], fill=tuple(int(v * 0.8) for v in c[:3]) + (255,), width=1)
    img.save(f"{OUT}/leaf_card.png")
    print("wrote leaf_card")


def bark(n=512, tile=1.0):
    mpp = tile / n
    fiss = fbm(n, 3, 5, seed=101, aniso=(1.0, 0.18))
    col = tint(hexrgb("#5f5245"), 0.18 * fiss + 0.06 * band_noise(n, 60, 200, seed=102))
    h = 0.01 * np.clip(fiss, -1.5, 1.5)
    save("bark", col, normal_from_height(h, mpp), 0.9 + 0.04 * fiss)


if __name__ == "__main__":
    siding()
    shingles()
    concrete("concrete", color="#aaa69c")
    concrete("drive", color="#a39d92", stains=0.12, speck=0.06, tile=3.0)
    concrete("foundation", color="#9f9a90", stains=0.08, tile=1.5)
    asphalt()
    mulch()
    fence()
    lawn()
    pavers()
    leafy("shrub")
    leaf_card()
    bark()
