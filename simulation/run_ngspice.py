#!/usr/bin/env python3
"""
run_ngspice.py - Run the same netlist in ngspice (no LTspice needed) and plot AC + step response.

  sudo apt install ngspice          # or: brew install ngspice
  python simulation/run_ngspice.py  # writes docs/images/sim_ac.png, sim_step.png

The LTspice-only directives (.meas, .noise, .step ...) are stripped automatically.
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
img = os.path.join(here, "..", "docs", "images")
os.makedirs(img, exist_ok=True)

src = open(os.path.join(here, "ina_filter_full.cir")).read().splitlines()
keep = [l for l in src if not re.match(r"^\.(meas|ac|tran|noise|op|end)\b", l, re.I)]

with tempfile.TemporaryDirectory() as tmp:
    ac_file, tr_file = os.path.join(tmp, "ac.txt"), os.path.join(tmp, "tran.txt")
    deck = "\n".join(keep) + f"""
.control
ac dec 100 1 1meg
wrdata {ac_file} vdb(adc) vp(adc)
tran 5u 20m
wrdata {tr_file} v(adc) v(sig)
.endc
.end
"""
    deck_path = os.path.join(tmp, "deck.cir")
    open(deck_path, "w").write(deck)
    # the .include line is relative to the simulation folder
    r = subprocess.run(["ngspice", "-b", deck_path], cwd=here, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(ac_file):
        sys.exit("ngspice failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    ac = np.loadtxt(ac_file)
    tr = np.loadtxt(tr_file)

f, gdb = ac[:, 0], ac[:, 1]
g0 = gdb[0]
i = int(np.argmax(gdb < g0 - 3.0103))
f3 = float(np.exp(np.interp(g0 - 3.0103, [gdb[i], gdb[i - 1]], [np.log(f[i]), np.log(f[i - 1])])))
print(f"DC-ish gain {g0:.2f} dB ({10**(g0/20):.1f} V/V), -3 dB at {f3:.0f} Hz")

fig, ax = plt.subplots(figsize=(7, 4))
ax.semilogx(f, gdb); ax.axvline(f3, ls="--", c="gray", lw=0.8)
ax.set(xlabel="Frequency (Hz)", ylabel="Gain (dB)", ylim=(-20, 45),
       title=f"ngspice AC response: {g0:.1f} dB, -3 dB at {f3:.0f} Hz")
ax.grid(True, which="both", alpha=0.3); fig.tight_layout(); fig.savefig(os.path.join(img, "sim_ac.png"), dpi=150)

t, vadc = tr[:, 0], tr[:, 1]
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(t * 1e3, vadc, label="ADC node")
ax.plot(t * 1e3, 1.65 + 100.238 * tr[:, 3], lw=0.8, ls="--", label="ideal x100 (unfiltered)")
ax.set(xlabel="Time (ms)", ylabel="Voltage (V)", title="ngspice step response, +/-10 mV differential step")
ax.legend(); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(os.path.join(img, "sim_step.png"), dpi=150)
print(f"overshoot: max {vadc.max():.3f} V, min {vadc.min():.3f} V")
