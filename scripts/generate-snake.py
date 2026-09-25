import argparse, datetime, json, math, random
from collections import deque

PALETTES = {
    "dark": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    "light": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
}
SNAKE = {"dark": ("#39d353", "#0d3d1f"), "light": ("#2da44e", "#a7e0b6")}

CELL, GAP = 13, 3
PITCH = CELL + GAP
R = 7
POP = 0.035          # time the snake holds while the graph pops in
ROUNDS = 12          # snack rounds after the board is cleared
BATCH = 8            # snacks spawned per round
HUNT_RADIUS = 14     # snacks spawn within reach of the snake


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


def nbrs(cell, C):
    c, r = cell
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nc, nr = c + dc, r + dr
        if 0 <= nc < C and 0 <= nr < R:
            yield (nc, nr)


def free_neighbors(cell, visited, C):
    return [n for n in nbrs(cell, C) if n not in visited]


def wander_path(C, rng):
    start = (0, 0)
    visited = {start}
    path = [start]
    while len(path) < C * R:
        cand = free_neighbors(path[-1], visited, C)
        if not cand:
            break
        cand.sort(key=lambda x: (len(free_neighbors(x, visited | {x}, C)), rng.random()))
        path.append(cand[0])
        visited.add(cand[0])
    return path


def bfs_all(start, C):
    dist = {start: 0}
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nb in nbrs(cur, C):
            if nb not in dist:
                dist[nb] = dist[cur] + 1
                prev[nb] = cur
                q.append(nb)
    return dist, prev


def reconstruct(prev, goal):
    out = []
    cur = goal
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    return out[::-1]


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
            elif rng.random() < 0.82:
                grid[c][r] = rng.choices([1, 2, 3, 4], [0.5, 0.3, 0.15, 0.05])[0]

    counts = [grid[c][r] for c in range(C) for r in range(R)]
    th = quartile_levels(counts)
    colors = PALETTES[palette_name]
    snake_col, snake_edge = SNAKE[palette_name]
    cells = [(c, r) for c in range(C) for r in range(R)]

    # phase 1: clear the whole board, spiral from the top-left
    pts1 = wander_path(C, rng)
    path = list(pts1)
    e1 = {cell: i for i, cell in enumerate(pts1)}

    # phase 2: keep spawning snacks and hunt them nearest-first over shortest paths
    events = {cell: [] for cell in cells}
    used = set()
    current = pts1[-1]
    for _ in range(ROUNDS):
        avail = [c for c in cells if c not in used]
        if len(avail) < BATCH:
            break
        spawn_idx = len(path) - 1
        pending = {}
        near = [c for c in avail
                if abs(c[0] - current[0]) + abs(c[1] - current[1]) <= HUNT_RADIUS]
        pool = near if len(near) >= BATCH else avail
        for t in rng.sample(pool, min(BATCH, len(pool))):
            pending[t] = spawn_idx
            used.add(t)
        while pending:
            dist, prev = bfs_all(current, C)
            tgt = min(pending, key=lambda c: dist.get(c, 10 ** 9))
            for cell in reconstruct(prev, tgt)[1:]:
                path.append(cell)
                if cell in pending:
                    events[cell].append((pending.pop(cell), len(path) - 1))
            current = tgt

    # phase 3: glide back to the start so the loop is seamless
    for cell in reconstruct(bfs_all(current, C)[1], (0, 0))[1:]:
        path.append(cell)

    N = len(path)
    if N < 2:
        raise SystemExit("path too short")
    D = round(max(28.0, (N - 1) * 0.042), 1)

    def t(i):
        return min(0.9995, POP + (1 - POP) * i / (N - 1))

    print(f"steps={N - 1} D={D}s phase1_end={t(len(pts1) - 1):.3f} "
          f"snacks={sum(len(v) for v in events.values())} cells={C * R}")

    def cell_rect(c, r):
        lvl = level_of(grid[c][r], th)
        col, empty = colors[lvl], colors[0]
        kf = [(0.0, empty), (max(0.0006, rng.random() * 0.028), col), (t(e1[(c, r)]), empty)]
        for si, ei in events[(c, r)]:
            kf.append((t(si), col))
            kf.append((t(ei), empty))
        for i in range(1, len(kf)):
            kf[i] = (max(kf[i][0], kf[i - 1][0] + 0.0008), kf[i][1])

        key_times = ";".join(f"{k:.4f}" for k, _ in kf)
        values = ";".join(v for _, v in kf)
        return (f'<rect x="{c*PITCH:.1f}" y="{r*PITCH:.1f}" width="{CELL}" height="{CELL}" rx="2.6" fill="{col}">'
                f'<animate attributeName="fill" calcMode="discrete" values="{values}" keyTimes="{key_times}" '
                f'dur="{D}s" repeatCount="indefinite"/></rect>')

    rects = "".join(cell_rect(c, r) for c, r in cells)

    d = "M " + " L ".join(f"{c*PITCH+CELL/2:.1f} {r*PITCH+CELL/2:.1f}" for c, r in path)
    total = (N - 1) * PITCH
    trail = 7 * PITCH
    dash = f'{trail} {total + trail:.1f}'
    off_from, off_to = f'{trail:.1f}', f'{trail - total:.1f}'

    pad = 8
    vw, vh = W + 2 * pad, H + 2 * pad
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{vw}" height="{vh}" viewBox="{-pad} {-pad} {vw} {vh}">
<defs><path id="mp" d="{d}" fill="none"/></defs>
<g>{rects}</g>
<path d="{d}" fill="none" stroke="{snake_edge}" stroke-width="{CELL*0.86:.1f}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}" opacity="0.8">
<animate attributeName="stroke-dashoffset" calcMode="linear" values="{off_from};{off_from};{off_to}" keyTimes="0;{POP};1" dur="{D}s" repeatCount="indefinite"/>
</path>
<path d="{d}" fill="none" stroke="{snake_col}" stroke-width="{CELL*0.62:.1f}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}">
<animate attributeName="stroke-dashoffset" calcMode="linear" values="{off_from};{off_from};{off_to}" keyTimes="0;{POP};1" dur="{D}s" repeatCount="indefinite"/>
</path>
<g>
<animateMotion dur="{D}s" repeatCount="indefinite" rotate="auto" calcMode="linear" keyPoints="0;0;1" keyTimes="0;{POP};1"><mpath xlink:href="#mp"/></animateMotion>
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
    svg = build(cal, args.palette)
    open(args.out, "w").write(svg)
    print(f"wrote {args.out}  {len(svg)} bytes")
