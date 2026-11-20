"""Minimal figure: zeta on the critical line, via Hardy's Z(t) = e^{i theta(t)} zeta(1/2 + i t) (real-valued).
Every sign change of Z is a zero of zeta on Re(s) = 1/2. Usage: zeta_fig.py out.svg"""
import mpmath as mp, sys
mp.mp.dps = 15
T1, N = 60.0, 1800
TEAL, ORANGE, GREY = "#178a94", "#d4782a", "#9aa0a6"
W, H, L, R, T, B = 1080, 300, 30, 30, 34, 44
Y0 = 150                                            # axis
SY = 30                                              # px per unit of Z
x = lambda t: L + (W - L - R) * t / T1
y = lambda v: Y0 - SY * v
pts = [(x(T1 * i / N), y(float(mp.siegelz(T1 * i / N)))) for i in range(N + 1)]
zeros, k = [], 1
while True:
    g = float(mp.im(mp.zetazero(k)))
    if g > T1: break
    zeros.append(g); k += 1
d = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in pts)
o = [f'<svg class="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
     f'aria-label="Hardy Z function on the critical line for 0 to {T1:g}, crossing zero at the first {len(zeros)} zeta zeros">']
o.append(f'<line x1="{L}" x2="{W-R}" y1="{Y0}" y2="{Y0}" stroke="{GREY}" stroke-opacity=".55" stroke-width=".8"/>')
for g in zeros:
    o.append(f'<line x1="{x(g):.1f}" x2="{x(g):.1f}" y1="{T}" y2="{H-B}" stroke="{GREY}" stroke-opacity=".18" stroke-width=".8" stroke-dasharray="2 4"/>')
o.append(f'<path d="{d}" fill="none" stroke="{TEAL}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>')
for i, g in enumerate(zeros):
    o.append(f'<circle cx="{x(g):.1f}" cy="{Y0}" r="3.6" fill="{ORANGE}"/>')
for i in (0, 1, 2):
    g = zeros[i]
    o.append(f'<text x="{x(g):.1f}" y="{H-B+20}" text-anchor="middle" class="fig-cap">{g:.2f}</text>')
o.append(f'<text x="{x(zeros[0]):.1f}" y="{T-12}" text-anchor="middle" class="fig-lab">γ<tspan baseline-shift="sub" font-size="12">1</tspan></text>')
o.append(f'<text x="{x(zeros[-1]):.1f}" y="{T-12}" text-anchor="middle" class="fig-lab">γ<tspan baseline-shift="sub" font-size="12">{len(zeros)}</tspan></text>')
o.append(f'<text x="{L}" y="{H-B+20}" class="fig-cap">0</text>')
o.append(f'<text x="{W-R}" y="{H-B+20}" text-anchor="end" class="fig-cap">t = {T1:g}</text>')
o.append(f'<text x="{L}" y="{T-12}" class="fig-lab">Z(t)</text>')
o.append('</svg>')
open(sys.argv[1], "w").write("\n".join(o))
print(len(zeros), "zeros; Z range", min(p[1] for p in pts), max(p[1] for p in pts))
