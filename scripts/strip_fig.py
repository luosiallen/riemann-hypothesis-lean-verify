"""Minimal critical-strip diagram for the dashboard (zeros computed with mpmath). Usage: strip_fig.py out.svg"""
import mpmath as mp, sys
TEAL, ORANGE = "#178a94", "#e07b2c"
W, H = 1080, 520
U = 250
OX, OY = 540 - U / 2, 440            # Re s = 0 at OX, so the strip is centred
X = lambda r: OX + U * r
top, bot = 34, H - 14
zeros = [float(mp.im(mp.zetazero(k))) for k in range(1, 9)]
TS = (OY - top - 48) / zeros[-1]
Y = lambda g: OY - TS * g
LBL_R, LBL_L = X(1) + 64, X(0) - 64   # annotation columns
o = [f'<svg class="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
     'aria-label="The critical strip 0 &lt; Re s &lt; 1, with the critical line Re s = 1/2 and the first zeros of zeta on it">',
     '<defs>'
     f'<linearGradient id="sg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{TEAL}" stop-opacity=".22"/><stop offset=".8" stop-color="{TEAL}" stop-opacity=".05"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></linearGradient>'
     f'<linearGradient id="lg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{ORANGE}"/><stop offset=".85" stop-color="{ORANGE}" stop-opacity=".55"/><stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></linearGradient>'
     f'<linearGradient id="eg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{TEAL}" stop-opacity=".7"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></linearGradient>'
     '<filter id="glow" x="-200%" y="-5%" width="500%" height="110%"><feGaussianBlur stdDeviation="4"/></filter>'
     '<marker id="ak" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1,1 L9,5 L1,9" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></marker>'
     '</defs>']
# strip
o.append(f'<rect class="strip" x="{X(0)}" y="{top}" width="{U}" height="{bot-top}" fill="url(#sg)"/>')
o.append(f'<rect x="{X(1)-.5}" y="{top}" width="1" height="{bot-top}" fill="url(#eg)"/>')
# imaginary axis = left edge of the strip
o.append(f'<line x1="{X(0)}" x2="{X(0)}" y1="{bot}" y2="{top+4}" stroke="currentColor" stroke-opacity=".45" stroke-width="1" marker-end="url(#ak)"/>')
o.append(f'<text x="{X(0)-12}" y="{top+14}" text-anchor="end" class="fig-num">Im <tspan font-style="italic">s</tspan></text>')
# real axis
o.append(f'<line x1="{X(-1.5)}" x2="{X(2.55)}" y1="{OY}" y2="{OY}" stroke="currentColor" stroke-opacity=".45" stroke-width="1" marker-end="url(#ak)"/>')
o.append(f'<text x="{X(2.55)+12}" y="{OY+5}" class="fig-num">Re <tspan font-style="italic">s</tspan></text>')
for r, lab in ((-1, "−1"), (0, "0"), (0.5, "½"), (1, "1"), (2, "2")):
    if r not in (0, 0.5):
        o.append(f'<line x1="{X(r)}" x2="{X(r)}" y1="{OY-4}" y2="{OY+4}" stroke="currentColor" stroke-opacity=".45" stroke-width="1"/>')
    dx, anc = {0: (-10, "end"), 0.5: (9, "start")}.get(r, (0, "middle"))
    o.append(f'<text x="{X(r)+dx}" y="{OY+28}" text-anchor="{anc}" class="fig-num">{lab}</text>')
# critical line with glow
o.append(f'<rect x="{X(.5)-3}" y="{top}" width="6" height="{bot-top}" fill="url(#lg)" opacity=".55" filter="url(#glow)"/>')
o.append(f'<rect x="{X(.5)-.9}" y="{top}" width="1.8" height="{bot-top}" fill="url(#lg)"/>')
# zeros
for i, g in enumerate(zeros):
    a = 1 - 0.45 * i / (len(zeros) - 1)
    o.append(f'<circle cx="{X(.5)}" cy="{Y(g):.1f}" r="8.5" fill="none" stroke="{ORANGE}" stroke-opacity="{.35*a:.2f}" stroke-width="1"/>')
    o.append(f'<circle cx="{X(.5)}" cy="{Y(g):.1f}" r="3.8" fill="{ORANGE}" fill-opacity="{a:.2f}"/>')
def note(x0, x1, y, head, sub, anchor):
    o.append(f'<line x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}" stroke="currentColor" stroke-opacity=".3" stroke-width=".8"/>')
    o.append(f'<circle cx="{x0}" cy="{y:.1f}" r="1.6" fill="currentColor" fill-opacity=".5"/>')
    tx = x1 + (10 if anchor == "start" else -10)
    o.append(f'<text x="{tx}" y="{y-3:.1f}" text-anchor="{anchor}" class="fig-txt">{head}</text>')
    o.append(f'<text x="{tx}" y="{y+17:.1f}" text-anchor="{anchor}" class="fig-sub">{sub}</text>')
note(X(.5) + 14, LBL_R, Y(zeros[5]), "nontrivial zeros", 'ζ(<tspan font-style="italic">s</tspan>) = 0', "start")
note(X(1) + 0, LBL_R, OY - 0.42 * (OY - top), "critical strip", '0 &lt; Re <tspan font-style="italic">s</tspan> &lt; 1', "start")
note(X(.5) - 6, LBL_L, OY - 0.22 * (OY - top), "critical line", 'Re <tspan font-style="italic">s</tspan> = ½', "end")
o.append('</svg>')
open(sys.argv[1], "w").write("\n".join(o))
