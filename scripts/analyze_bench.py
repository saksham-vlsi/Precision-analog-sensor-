#!/usr/bin/env python3
"""
analyze_bench.py - Turn bench measurements (CSV) into numbers and plots.

  python scripts/analyze_bench.py gain  measurements/gain_sweep.csv
  python scripts/analyze_bench.py freq  measurements/freq_response.csv
  python scripts/analyze_bench.py cmrr  measurements/cmrr.csv --gain 100.2
  python scripts/analyze_bench.py noise measurements/noise_scope.csv --gain 100.2
  python scripts/analyze_bench.py adc   measurements/adc_readback.csv

CSV formats (header row required, see measurements/*.csv templates):
  gain  : vin_mV, vout_V              (vin = DMM across bridge, vout = DMM at ADC node)
  freq  : freq_Hz, vin_mVpp, vout_mVpp
  cmrr  : freq_Hz, vcm_Vpp, vout_mVpp (both inputs tied together, common-mode drive)
  noise : one column of scope samples in volts (header optional), or time,volts
  adc   : applied_uV, reported_uV     (firmware 'vin_uV' column vs DMM-measured input)
Add --plot to save a PNG into docs/images/.
"""
import argparse
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design_calc as dc  # noqa: E402

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "images")


def load(path, ncols=None):
    rows = []
    with open(path, newline="") as f:
        for r in csv.reader(f):
            if not r or r[0].lstrip().startswith("#"):
                continue
            try:
                rows.append([float(x) for x in r])
            except ValueError:
                continue                      # header line
    if not rows:
        sys.exit(f"No numeric rows found in {path} - fill in the template first.")
    a = np.array(rows)
    if ncols and a.shape[1] < ncols:
        sys.exit(f"{path}: expected at least {ncols} numeric columns")
    return a


def save(fig, name, plot):
    if plot:
        import matplotlib.pyplot as plt  # noqa: F401
        os.makedirs(IMG, exist_ok=True)
        fig.tight_layout()
        fig.savefig(os.path.join(IMG, name), dpi=150)
        print(f"plot saved: docs/images/{name}")


def cmd_gain(a, args):
    d = dc.design()
    g_nom = dc.ina_gain(d["r1"], d["rg"], d["r2"], d["r3"])
    vin, vout = a[:, 0] * 1e-3, a[:, 1]
    g, off = np.polyfit(vin, vout, 1)
    resid = vout - (g * vin + off)
    fs = (vin.max() - vin.min()) * g
    print(f"measured gain      : {g:.3f} V/V  (nominal {g_nom:.3f}, error {100*(g-g_nom)/g_nom:+.2f} %)")
    print(f"output at Vin = 0  : {off:.4f} V (ideal {dc.VCM:.3f} V, offset {1e3*(off-dc.VCM):+.1f} mV)")
    print(f"input-ref. offset  : {1e6*(off-dc.VCM)/g:+.1f} uV")
    print(f"max nonlinearity   : {1e3*np.abs(resid).max():.2f} mV = {100*np.abs(resid).max()/fs:.3f} % of span")
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    ax[0].plot(vin * 1e3, vout, "o", label="measured")
    ax[0].plot(vin * 1e3, g * vin + off, "-", label=f"fit: {g:.2f} V/V")
    ax[0].set(xlabel="Differential input (mV)", ylabel="Output (V)", title="DC transfer"); ax[0].legend()
    ax[1].plot(vin * 1e3, resid * 1e3, "o-")
    ax[1].set(xlabel="Differential input (mV)", ylabel="Residual (mV)", title="Linearity residual")
    for x in ax: x.grid(alpha=0.3)
    save(fig, "bench_gain.png", args.plot)


def cmd_freq(a, args):
    f, vin, vout = a[:, 0], a[:, 1], a[:, 2]
    gdb = 20 * np.log10(vout / vin)
    ref = gdb[np.argmin(f)]
    below = np.where(gdb <= ref - 3.0103)[0]
    print(f"gain at {f.min():g} Hz : {ref:.2f} dB ({10**(ref/20):.1f} V/V)")
    if below.size:
        i = below[0]
        f3 = np.interp(ref - 3.0103, [gdb[i], gdb[i - 1]], [f[i], f[i - 1]])
        print(f"-3 dB frequency   : {f3:.0f} Hz")
    else:
        print("-3 dB point not reached - extend the sweep to higher frequency")
    d = dc.design()
    ff = np.logspace(math.log10(f.min()), math.log10(f.max()), 400)
    calc = 20 * np.log10(dc.ina_gain(d["r1"], d["rg"], d["r2"], d["r3"]) *
                         np.abs(dc.sk_h(ff, d["rf"], d["rf"], d["c1"], d["c2"])))
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.semilogx(ff, calc, "--", label="calculated (ideal)")
    ax.semilogx(f, gdb, "o-", label="measured")
    ax.set(xlabel="Frequency (Hz)", ylabel="Gain (dB)", title="Frequency response"); ax.legend(); ax.grid(True, which="both", alpha=0.3)
    save(fig, "bench_freq.png", args.plot)


def cmd_cmrr(a, args):
    f, vcm, vout = a[:, 0], a[:, 1], a[:, 2] * 1e-3
    cm = 20 * np.log10(args.gain * vcm / vout)
    for fi, ci in zip(f, cm):
        print(f"{fi:8.1f} Hz : CMRR = {ci:6.1f} dB")
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.semilogx(f, cm, "o-"); ax.set(xlabel="Frequency (Hz)", ylabel="CMRR (dB)", title="Measured CMRR"); ax.grid(True, which="both", alpha=0.3)
    save(fig, "bench_cmrr.png", args.plot)


def cmd_noise(a, args):
    v = a[:, -1]
    v = v - v.mean()
    rms, pp = v.std(), v.max() - v.min()
    print(f"samples            : {v.size}")
    print(f"output noise       : {rms*1e6:.1f} uV rms, {pp*1e6:.0f} uV pk-pk")
    print(f"input-referred     : {rms/args.gain*1e6:.3f} uV rms, {pp/args.gain*1e6:.2f} uV pk-pk")
    print("note: if this is near your scope's own noise floor (short the probe to see it) treat it as an upper bound.")


def cmd_adc(a, args):
    app, rep = a[:, 0], a[:, 1]
    err = rep - app
    print(f"mean error  : {err.mean():+.1f} uV   max |error| : {np.abs(err).max():.1f} uV"
          f" ({100*np.abs(err).max()/(app.max()-app.min()):.3f} % of span)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["gain", "freq", "cmrr", "noise", "adc"])
    ap.add_argument("csv")
    ap.add_argument("--gain", type=float, default=100.238, help="gain used for CMRR / input-referred noise")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    a = load(args.csv)
    {"gain": cmd_gain, "freq": cmd_freq, "cmrr": cmd_cmrr, "noise": cmd_noise, "adc": cmd_adc}[args.kind](a, args)


if __name__ == "__main__":
    main()
