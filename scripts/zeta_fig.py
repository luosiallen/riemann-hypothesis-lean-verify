"""Minimal 3-panel figure: the curve t -> zeta(sigma + i t) for sigma = 0.3, 1/2, 0.7.
Only on the critical line does the curve pass through the origin (the nontrivial zeros)."""
import mpmath as mp, math, sys
mp.mp.dps = 15
T0, T1, N = 0.0, 42.0, 1500
TEAL, ORANGE, GREY = "#178a94", "#d4782a", "#9aa0a6"
panels = [(0.3, "0.3"), (0.5, "½"), (0.7, "0.7")]
W, H, PW = 1080, 390, 280          # canvas, panel width
CX = [170, 540, 910]; CY = 205
S = 34                              # px per unit (same scale in all panels)
zeros = [float(mp.im(mp.zetazero(k))) for k in range(1, 12) if mp.im(mp.zetazero(k)) < T1]
out = [f'<svg class="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
       f'aria-label="The curve zeta(sigma+it) for sigma 0.3, one half and 0.7; only at one half does it pass through the origin">',
       '<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
       f'<path d="M0,1 L9,5 L0,9 z" fill="{GREY}"/></marker>'
       '<marker id="tip" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto">'
       f'<path d="M0,1 L9,5 L0,9 z" fill="{TEAL}"/></marker></defs>']
for (sig, lab), cx in zip(panels, CX):
    pts = []
    for i in range(N + 1):
        t = T0 + (T1 - T0) * i / N
        z = complex(mp.zeta(mp.mpc(sig, t)))
        x, y = cx + S * z.real, CY - S * z.imag
        x = max(cx - PW / 2 - 10, min(cx + PW / 2 + 10, x)); y = max(48, min(H - 30, y))
        pts.append((x, y))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out.append(f'<ellipse cx="{cx}" cy="{CY}" rx="{PW/2-6}" ry="{PW/2-6}" fill="currentColor" fill-opacity=".018" stroke="{GREY}" stroke-opacity=".28" stroke-width=".8"/>')
    out.append(f'<line x1="{cx-PW/2+6}" x2="{cx+PW/2-6}" y1="{CY}" y2="{CY}" stroke="{GREY}" stroke-opacity=".35" stroke-width=".7" stroke-dasharray="2 4"/>')
    out.append(f'<line x1="{cx}" x2="{cx}" y1="{CY-PW/2+6}" y2="{CY+PW/2-6}" stroke="{GREY}" stroke-opacity=".35" stroke-width=".7" stroke-dasharray="2 4"/>')
    out.append(f'<path d="{d}" fill="none" stroke="{TEAL}" stroke-width="1.15" stroke-opacity=".9" stroke-linejoin="round" stroke-linecap="round" marker-end="url(#tip)"/>')
    # small direction dots along the curve
    for k in range(40, N, 150):
        x, y = pts[k]; out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="{TEAL}"/>')
    if sig == 0.5:
        out.append(f'<circle cx="{cx}" cy="{CY}" r="4.2" fill="{ORANGE}"/>')
        out.append(f'<circle cx="{cx}" cy="{CY}" r="9" fill="none" stroke="{ORANGE}" stroke-opacity=".45" stroke-width=".9"/>')
        out.append(f'<text x="{cx}" y="{CY+PW/2+22}" text-anchor="middle" class="fig-cap">passes through 0 · {len(zeros)} zeros</text>')
    else:
        out.append(f'<circle cx="{cx}" cy="{CY}" r="2.4" fill="none" stroke="{GREY}" stroke-width="1"/>')
        out.append(f'<text x="{cx}" y="{CY+PW/2+22}" text-anchor="middle" class="fig-cap">never 0</text>')
    out.append(f'<text x="{cx}" y="30" text-anchor="middle" class="fig-lab"><tspan font-style="italic">σ</tspan> = {lab}</text>')
for a, b in [(CX[0] + PW/2 + 14, CX[1] - PW/2 - 14), (CX[1] + PW/2 + 14, CX[2] - PW/2 - 14)]:
    out.append(f'<line x1="{a}" x2="{b}" y1="{CY}" y2="{CY}" stroke="{GREY}" stroke-width="1.2" marker-end="url(#ah)"/>')
out.append('</svg>')
open(sys.argv[1], "w").write("\n".join(out))
print("zeros below T:", len(zeros))
