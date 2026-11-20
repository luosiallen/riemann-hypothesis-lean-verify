"""Minimal critical-strip diagram for the dashboard. Zeros on the critical line are computed with mpmath.
Usage: strip_fig.py out.svg"""
import mpmath as mp, sys
TEAL, ORANGE, GREY, INK = "#178a94", "#d4782a", "#9aa0a6", "currentColor"
W, H = 1080, 470
U, OX, OY = 230, 430, 390          # px per real unit, origin
X = lambda r: OX + U * r
TS = 8.6                            # px per unit of imaginary part
zeros = [float(mp.im(mp.zetazero(k))) for k in range(1, 6)]
top, bot = 46, H - 20
o = [f'<svg class="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
     'aria-label="The critical strip 0 &lt; Re(s) &lt; 1 with the critical line Re(s) = 1/2 and the first five zeta zeros on it">',
     '<defs>'
     f'<linearGradient id="sg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{TEAL}" stop-opacity=".16"/><stop offset="1" stop-color="{TEAL}" stop-opacity=".03"/></linearGradient>'
     f'<marker id="ak" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0.5 L10,5 L0,9.5 L2.5,5 z" fill="{INK}"/></marker>'
     f'<marker id="ao" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0.5 L10,5 L0,9.5 L2.5,5 z" fill="{ORANGE}"/></marker>'
     '</defs>']
# strip
o.append(f'<rect x="{X(0)}" y="{top+16}" width="{U}" height="{bot-top-16}" fill="url(#sg)"/>')
# real axis
o.append(f'<line x1="40" x2="{W-120}" y1="{OY}" y2="{OY}" stroke="{INK}" stroke-width="1" marker-end="url(#ak)"/>')
o.append(f'<text x="{W-110}" y="{OY+5}" class="fig-txt">real axis</text>')
# Re = 0 and Re = 1 boundaries (axes)
for r in (0, 1):
    o.append(f'<line x1="{X(r)}" x2="{X(r)}" y1="{bot}" y2="{top}" stroke="{INK}" stroke-width="1" marker-end="url(#ak)"/>')
o.append(f'<text x="{X(0)}" y="{top-14}" text-anchor="middle" class="fig-txt">imaginary axis</text>')
# critical line
o.append(f'<line x1="{X(.5)}" x2="{X(.5)}" y1="{bot}" y2="{top+22}" stroke="{ORANGE}" stroke-width="1.6" marker-end="url(#ao)"/>')
# ticks
for r, lab in ((-1, "−1"), (0, "0"), (0.5, "½"), (1, "1"), (2, "2")):
    o.append(f'<line x1="{X(r)}" x2="{X(r)}" y1="{OY-5}" y2="{OY+5}" stroke="{INK}" stroke-width="1"/>')
    o.append(f'<text x="{X(r)+(10 if r in (0,0.5,1) else 0)}" y="{OY+24}" text-anchor="{"start" if r in (0,0.5,1) else "middle"}" class="fig-num">{lab}</text>')
# zeros
for i, g in enumerate(zeros):
    y = OY - TS * g
    o.append(f'<circle cx="{X(.5)}" cy="{y:.1f}" r="4" fill="{ORANGE}"/>')
    o.append(f'<text x="{X(.5)+14}" y="{y+4:.1f}" class="fig-cap">½ + {g:.2f} i</text>')
# brace over the strip
by = top + 4
o.append(f'<path d="M{X(0)+4},{by+12} q0,-8 8,-8 h{U/2-20} q8,0 8,-8 q0,8 8,8 h{U/2-20} q8,0 8,8" fill="none" stroke="{INK}" stroke-width="1"/>')
o.append(f'<line x1="{X(.5)+8}" y1="{by-6}" x2="{X(1)+60}" y2="{by-26}" stroke="{INK}" stroke-width=".8"/>')
o.append(f'<text x="{X(1)+66}" y="{by-22}" class="fig-txt">critical strip  0 &lt; Re(<tspan font-style="italic">s</tspan>) &lt; 1</text>')
# critical line label
ly = OY - 70
o.append(f'<line x1="{X(.5)-4}" y1="{ly}" x2="{X(0)-60}" y2="{ly-22}" stroke="{INK}" stroke-width=".8"/>')
o.append(f'<text x="{X(0)-66}" y="{ly-18}" text-anchor="end" class="fig-txt">critical line  Re(<tspan font-style="italic">s</tspan>) = ½</text>')
o.append('</svg>')
open(sys.argv[1], "w").write("\n".join(o))
print("zeros", zeros)
