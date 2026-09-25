import argparse, datetime, json, math, random

PALETTES = {
    "dark": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    "light": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
}
SNAKE = {"dark": ("#39d353", "#0d3d1f"), "light": ("#2da44e", "#a7e0b6")}

CELL, GAP = 13, 3
PITCH = CELL + GAP
R = 7


def quartile_levels(counts):
    nz = sorted(c for c in counts if c > 0)
    if not nz:
        return [0] * 5

    def q(p):
        return nz[min(len(nz) - 1, int(len(nz) * p))]
    return [-1, q(0.25), q(0.5), q(0.75), nz[-1]]


def level_of(c, th):
    if c <= 0:
        return 0
    return 1 if c <= th[1] else 2 if c <= th[2] else 3 if c <= th[3] else 4


def neighbors(cell, visited, C):
    c, r = cell
    out = []
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nc, nr = c + dc, r + dr
        if 0 <= nc < C and 0 <= nr < R and (nc, nr) not in visited:
            out.append((nc, nr))
    return out


def wander_path(C, rng):
    start = (0, 0)
    visited = {start}
    path = [start]
    while len(path) < C * R:
        cand = neighbors(path[-1], visited, C)
        if not cand:
            break
        cand.sort(key=lambda x: (len(neighbors(x, visited | {x}, C)), rng.random()))
        path.append(cand[0])
        visited.add(cand[0])
    return path


def build(calendar, palette_name):
    weeks = calendar["weeks"]
    C = len(weeks)
    W, H = C * PITCH, R * PITCH

    real = [[0] * R for _ in range(C)]
    for ci, wk in enumerate(weeks):
        for day in wk["contributionDays"]:
            real[ci][day["weekday"]] = day["contributionCount"]

    seed = int(datetime.date.today().strftime("%Y%m%d"))
    rng = random.Random(seed)

    grid = [[0] * R for _ in range(C)]
    for c in range(C):
        for r in range(R):
            if real[c][r] > 0:
                grid[c][r] = real[c][r]
            elif rng.random() < 0.55:
                grid[c][r] = rng.choices([1, 2, 3, 4], [0.5, 0.3, 0.15, 0.05])[0]

    counts = [grid[c][r] for c in range(C) for r in range(R)]
    th = quartile_levels(counts)
    colors = PALETTES[palette_name]
    snake_col, snake_edge = SNAKE[palette_name]

    pts = wander_path(C, rng)
    total = (len(pts) - 1) * PITCH
    idx = {cell: i for i, cell in enumerate(pts)}

    def frac(cell):
        return idx.get(cell, 0) / (len(pts) - 1)

    dur = round(max(16.0, len(pts) * 0.06), 1)

    def cell_rect(c, r):
        lvl = level_of(grid[c][r], th)
        if (c, r) in idx:
            f = frac((c, r))
            a = min(max(f, 0.004), 0.985)
            b = min(a + 0.012, 0.999)
            col, empty = colors[lvl], colors[0]
            anim = (f'<animate attributeName="fill" values="{col};{col};{empty};{empty}" '
                    f'keyTimes="0;{a:.3f};{b:.3f};1" dur="{dur}s" repeatCount="indefinite"/>')
        else:
            col, anim = colors[lvl], ""
        return (f'<rect x="{c*PITCH:.1f}" y="{r*PITCH:.1f}" width="{CELL}" height="{CELL}" rx="2.6" '
                f'fill="{col}">{anim}</rect>')

    rects = "".join(cell_rect(c, r) for c in range(C) for r in range(R))

    d = "M " + " L ".join(f"{c*PITCH+CELL/2:.1f} {r*PITCH+CELL/2:.1f}" for c, r in pts)
    trail = 7 * PITCH
    dash = f'{trail} {total + trail:.1f}'
    off_from, off_to = f'{trail:.1f}', f'{trail - total:.1f}'

    pad = 8
    vw, vh = W + 2 * pad, H + 2 * pad
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{vw}" height="{vh}" viewBox="{-pad} {-pad} {vw} {vh}">
<defs><path id="mp" d="{d}" fill="none"/></defs>
<g>{rects}</g>
<path d="{d}" fill="none" stroke="{snake_edge}" stroke-width="{CELL*0.86:.1f}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}" opacity="0.8">
<animate attributeName="stroke-dashoffset" values="{off_from};{off_to}" dur="{dur}s" repeatCount="indefinite"/>
</path>
<path d="{d}" fill="none" stroke="{snake_col}" stroke-width="{CELL*0.62:.1f}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}">
<animate attributeName="stroke-dashoffset" values="{off_from};{off_to}" dur="{dur}s" repeatCount="indefinite"/>
</path>
<g>
<animateMotion dur="{dur}s" repeatCount="indefinite" rotate="auto"><mpath xlink:href="#mp"/></animateMotion>
<circle r="{CELL*0.62:.1f}" fill="{snake_col}" stroke="{snake_edge}" stroke-width="1"/>
<circle cx="2.4" cy="-3" r="2.1" fill="#fff"/><circle cx="3.3" cy="-3" r="1" fill="#0d1117"/>
<circle cx="2.4" cy="3" r="2.1" fill="#fff"/><circle cx="3.3" cy="3" r="1" fill="#0d1117"/>
<path d="M6 0 L9 -1.6 M6 0 L9 1.6" stroke="#ff4d4d" stroke-width="1" stroke-linecap="round"/>
</g>
</svg>'''


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--palette", choices=["dark", "light"], default="dark")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cal = json.load(open(args.input))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    C = len(cal["weeks"])
    cells = C * 7
    svg = build(cal, args.palette)
    open(args.out, "w").write(svg)
    print(f"wrote {args.out}  {len(svg)} bytes  cells={cells}")
