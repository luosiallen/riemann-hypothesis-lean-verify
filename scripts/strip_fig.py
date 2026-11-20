"""Minimal critical-strip diagram for the dashboard (zeros computed with mpmath). Usage: strip_fig.py out.svg"""
import mpmath as mp, sys
TEAL, ORANGE = "#178a94", "#d4782a"
W, H = 1080, 460
U, OX, OY = 220, 430, 380            # px per real unit, origin
X = lambda r: OX + U * r
TS = 6.2                             # px per unit of Im(s)
zeros = [float(mp.im(mp.zetazero(k))) for k in range(1, 11)]
top, bot = 40, H - 18
o = [f'<svg class="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
     'aria-label="The critical strip 0 &lt; Re s &lt; 1 with the critical line Re s = 1/2 and the first ten zeta zeros on it">',
     '<defs>'
     f'<linearGradient id="sg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{TEAL}" stop-opacity=".22"/><stop offset=".85" stop-color="{TEAL}" stop-opacity=".02"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></linearGradient>'
     f'<linearGradient id="lg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{ORANGE}" stop-opacity=".95"/><stop offset="1" stop-color="{ORANGE}" stop-opacity=".35"/></linearGradient>'
     f'<linearGradient id="bg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{TEAL}" stop-opacity=".6"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></linearGradient>'
     '<marker id="ak" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9" fill="none" stroke="currentColor" stroke-opacity=".55" stroke-width="1.2"/></marker>'
     '</defs>']
# strip + soft boundaries
o.append(f'<rect class="strip" x="{X(0)}" y="{top}" width="{U}" height="{bot-top}" fill="url(#sg)"/>')
for r in (0, 1):
    o.append(f'<rect x="{X(r)-0.4}" y="{top}" width=".8" height="{bot-top}" fill="url(#bg)"/>')
# real axis (hairline)
o.append(f'<line x1="60" x2="{W-90}" y1="{OY}" y2="{OY}" stroke="currentColor" stroke-opacity=".45" stroke-width=".9" marker-end="url(#ak)"/>')
o.append(f'<text x="{W-78}" y="{OY+5}" class="fig-num">Re <tspan font-style="italic">s</tspan></text>')
# imaginary axis label at top of Re=0
o.append(f'<text x="{X(0)-12}" y="{top+8}" text-anchor="end" class="fig-num">Im <tspan font-style="italic">s</tspan></text>')
# critical line
o.append(f'<rect x="{X(.5)-0.8}" y="{top}" width="1.6" height="{bot-top}" fill="url(#lg)"/>')
# ticks + numbers
for r, lab in ((-1, "−1"), (0, "0"), (0.5, "½"), (1, "1"), (2, "2")):
    o.append(f'<line x1="{X(r)}" x2="{X(r)}" y1="{OY-4}" y2="{OY+4}" stroke="currentColor" stroke-opacity=".45" stroke-width=".9"/>')
    o.append(f'<text x="{X(r)}" y="{OY+28}" text-anchor="middle" class="fig-num">{lab}</text>')
# zeros: dots with halo, fading upward
for i, g in enumerate(zeros):
    y = OY - TS * g; a = 1 - 0.55 * i / (len(zeros) - 1)
    o.append(f'<circle cx="{X(.5)}" cy="{y:.1f}" r="9" fill="{ORANGE}" fill-opacity="{.10*a:.3f}"/>')
    o.append(f'<circle cx="{X(.5)}" cy="{y:.1f}" r="3.4" fill="{ORANGE}" fill-opacity="{a:.2f}"/>')
# annotations
cy = OY - TS * 22
o.append(f'<line x1="{X(1)+10}" y1="{cy}" x2="{X(1)+70}" y2="{cy}" stroke="currentColor" stroke-opacity=".35" stroke-width=".8"/>')
o.append(f'<text x="{X(1)+80}" y="{cy-4}" class="fig-txt">critical strip</text>')
o.append(f'<text x="{X(1)+80}" y="{cy+16}" class="fig-sub">0 &lt; Re <tspan font-style="italic">s</tspan> &lt; 1</text>')
ly = OY - TS * 7
o.append(f'<line x1="{X(.5)-10}" y1="{ly}" x2="{X(0)-70}" y2="{ly}" stroke="currentColor" stroke-opacity=".35" stroke-width=".8"/>')
o.append(f'<text x="{X(0)-80}" y="{ly-4}" text-anchor="end" class="fig-txt">critical line</text>')
o.append(f'<text x="{X(0)-80}" y="{ly+16}" text-anchor="end" class="fig-sub">Re <tspan font-style="italic">s</tspan> = ½</text>')
zy = OY - TS * zeros[4]
o.append(f'<line x1="{X(.5)+14}" y1="{zy:.1f}" x2="{X(1)+70}" y2="{zy-40:.1f}" stroke="currentColor" stroke-opacity=".35" stroke-width=".8"/>')
o.append(f'<text x="{X(1)+80}" y="{zy-44:.1f}" class="fig-txt">nontrivial zeros</text>')
o.append(f'<text x="{X(1)+80}" y="{zy-24:.1f}" class="fig-sub">ζ(<tspan font-style="italic">s</tspan>) = 0</text>')
o.append('</svg>')
open(sys.argv[1], "w").write("\n".join(o))
