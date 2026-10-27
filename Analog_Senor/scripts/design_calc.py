#!/usr/bin/env python3
"""
design_calc.py - Design calculator for the Precision Analog Sensor Front-End
(3-op-amp instrumentation amplifier + 2nd-order Sallen-Key Butterworth LPF).

What it does
  1. Derives component values from the specs and snaps them to the E96 series.
  2. Reports gain, filter f0 / Q, output swing, ADC resolution.
  3. Monte-Carlo analysis of gain, CMRR (resistor mismatch only, ideal op-amps)
     and filter cutoff spread.
  4. First-order input-referred noise budget.
  5. Optionally writes plots to docs/images/ (--plot).

Usage
  python scripts/design_calc.py                 # design report
  python scripts/design_calc.py --mc 20000      # + Monte-Carlo
  python scripts/design_calc.py --mc 20000 --plot

Assumptions that you MUST check against the datasheet of the op-amp you use
are collected in the OPAMP dictionary below.
"""
import argparse
import math
import os

import numpy as np

# ----------------------------------------------------------------------------
# Specification
# ----------------------------------------------------------------------------
VDD = 3.3            # V, single supply (also STM32 ADC reference -> ratiometric)
VCM = VDD / 2        # V, bridge common-mode and output mid-rail reference
VD_FS = 10e-3        # V, +/- full-scale differential bridge output
G_TOTAL = 100.0      # V/V, target total gain
G2 = 5.0             # V/V, difference-amplifier gain (R3/R2)
FC_TARGET = 1000.0   # Hz, Butterworth low-pass target
R1 = 10e3            # ohm, INA input-stage feedback resistors (x2)
C2 = 10e-9           # F, Sallen-Key shunt capacitor
ADC_BITS = 12

# Op-amp parameters used ONLY for the noise/offset budget.  Values are typical
# for a low-voltage CMOS RRIO op-amp such as the TI TLV9064 - verify them.
OPAMP = dict(en_nV=10.0, vos_max_mV=1.6, name="TLV9064 (verify against datasheet)")

K_B = 1.380649e-23
T_K = 300.0

E96 = [1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30,
       1.33, 1.37, 1.40, 1.43, 1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74,
       1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10, 2.15, 2.21, 2.26, 2.32,
       2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
       3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12,
       4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49,
       5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32,
       7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76]
assert len(E96) == 96


def snap_e96(value):
    """Nearest E96 value (log distance)."""
    decade = 10 ** math.floor(math.log10(value))
    cands = [m * d for d in (decade / 10, decade, decade * 10) for m in E96]
    return min(cands, key=lambda c: abs(math.log(c / value)))


# ----------------------------------------------------------------------------
# Circuit equations
# ----------------------------------------------------------------------------
def ina_gain(r1, rg, r2, r3):
    """Total gain of the 3-op-amp INA: (1 + 2 R1/Rg) * (R3/R2)."""
    return (1 + 2 * r1 / rg) * (r3 / r2)


def ina_out(vp, vn, vref, r1a, r1b, rg, r2p, r3p, r2n, r3n):
    """Exact output of the INA with ideal op-amps and arbitrary resistors.

    Stage 1: o1 = vp + r1a*(vp-vn)/rg ;  o2 = vn - r1b*(vp-vn)/rg
    Stage 2: o1 -> r2p -> (+) , (+) -> r3p -> vref ;  o2 -> r2n -> (-) , (-) -> r3n -> out
    """
    i = (vp - vn) / rg
    o1 = vp + r1a * i
    o2 = vn - r1b * i
    v_plus = (o1 / r2p + vref / r3p) / (1 / r2p + 1 / r3p)
    return v_plus * (1 + r3n / r2n) - (r3n / r2n) * o2


def diff_gain(res, vref=VCM):
    return (ina_out(VCM + 5e-3, VCM - 5e-3, vref, **res) -
            ina_out(VCM - 5e-3, VCM + 5e-3, vref, **res)) / 20e-3


def cmrr_db(res, vcm=VCM, vref=VCM):
    """CMRR (dB) of the INA caused by resistor mismatch alone."""
    z = ina_out(vcm, vcm, vref, **res)
    acm = (ina_out(vcm + 0.5, vcm + 0.5, vref, **res) - z) / 0.5
    return 20 * math.log10(abs(diff_gain(res, vref)) / max(abs(acm), 1e-12))


def sk_params(r1, r2, c1, c2):
    """Unity-gain Sallen-Key low-pass: returns (f0, Q).
    c1 = feedback capacitor (node between resistors -> output), c2 = shunt capacitor."""
    w0 = 1 / math.sqrt(r1 * r2 * c1 * c2)
    q = math.sqrt(r1 * r2 * c1 * c2) / (c2 * (r1 + r2))
    return w0 / (2 * math.pi), q


def sk_h(f, r1, r2, c1, c2):
    s = 2j * np.pi * np.asarray(f)
    return 1 / (s ** 2 * r1 * r2 * c1 * c2 + s * c2 * (r1 + r2) + 1)


def f_3db(r1, r2, c1, c2):
    f = np.logspace(1, 5, 20001)
    mag = np.abs(sk_h(f, r1, r2, c1, c2))
    return float(f[np.argmax(mag < 1 / math.sqrt(2))])


# ----------------------------------------------------------------------------
# Design
# ----------------------------------------------------------------------------
def design():
    g1 = G_TOTAL / G2
    rg_ideal = 2 * R1 / (g1 - 1)
    rg = snap_e96(rg_ideal)
    r2 = 20e3
    r3 = r2 * G2
    c1 = 2 * C2                       # Butterworth: C1 = 2*C2 for equal R, unity gain
    rf_ideal = 1 / (2 * math.pi * FC_TARGET * C2 * math.sqrt(2))
    rf = snap_e96(rf_ideal)
    return dict(g1=g1, rg_ideal=rg_ideal, rg=rg, r1=R1, r2=r2, r3=r3,
                c1=c1, c2=C2, rf_ideal=rf_ideal, rf=rf)


def noise_budget(d, rs=500.0, rin=1e3):
    """First-order input-referred noise density (V/sqrt(Hz)) and integrated RMS."""
    kt4 = 4 * K_B * T_K
    en = OPAMP["en_nV"] * 1e-9
    g1 = 1 + 2 * d["r1"] / d["rg"]
    terms = {
        "A1+A2 voltage noise": 2 * en ** 2,
        "Source + input R, 2x(Rs+Rin)": kt4 * 2 * (rs + rin),
        "Rg thermal": kt4 * d["rg"],
        "R1 pair (referred by /G1)": kt4 * 2 * d["r1"] / g1 ** 2,
        "Stage-2 resistors (referred by /G1)": kt4 * 2 * (d["r2"] * d["r3"] / (d["r2"] + d["r3"])) / g1 ** 2,
        "A3 noise (referred by /G1)": (en * (1 + d["r3"] / d["r2"]) / g1) ** 2,
    }
    total = math.sqrt(sum(terms.values()))
    enbw = 1.11 * FC_TARGET           # 2nd-order Butterworth ENBW ~ 1.11 fc
    return terms, total, total * math.sqrt(enbw), enbw


def report(d):
    g1 = 1 + 2 * d["r1"] / d["rg"]
    g = ina_gain(d["r1"], d["rg"], d["r2"], d["r3"])
    f0, q = sk_params(d["rf"], d["rf"], d["c1"], d["c2"])
    lsb = VDD / 2 ** ADC_BITS
    out_swing = g * VD_FS
    print("=" * 74)
    print(" Precision Analog Sensor Front-End - design report")
    print("=" * 74)
    print(f" Supply / mid-rail            : {VDD:.2f} V / {VCM:.3f} V")
    print(f" Bridge full scale (diff)     : +/-{VD_FS*1e3:.1f} mV")
    print(f" Stage-1 gain target          : {d['g1']:.2f} -> Rg ideal {d['rg_ideal']:.1f} ohm -> E96 {d['rg']:.0f} ohm")
    print(f" Stage-1 gain (as built)      : {g1:.3f} V/V   [1 + 2*R1/Rg, R1 = {d['r1']/1e3:.0f}k]")
    print(f" Stage-2 gain                 : {d['r3']/d['r2']:.3f} V/V   [R3/R2 = {d['r3']/1e3:.0f}k/{d['r2']/1e3:.0f}k]")
    print(f" Total gain                   : {g:.3f} V/V ({20*math.log10(g):.2f} dB)")
    print(f" Output swing at +/-FS        : {VCM - out_swing:.3f} V ... {VCM + out_swing:.3f} V (rails 0 ... {VDD} V)")
    print(f" Filter                       : R ideal {d['rf_ideal']:.0f} ohm -> E96 {d['rf']/1e3:.2f}k, "
          f"C2 = {d['c2']*1e9:.0f} nF, C1 = {d['c1']*1e9:.0f} nF")
    print(f" Filter f0 / Q / f(-3 dB)     : {f0:.1f} Hz / {q:.4f} / {f_3db(d['rf'], d['rf'], d['c1'], d['c2']):.0f} Hz")
    print(f" ADC LSB (12-bit, {VDD} V)      : {lsb*1e3:.3f} mV at output = {lsb/g*1e6:.2f} uV input-referred")
    print(f" Counts across +/-FS          : {2*out_swing/lsb:.0f} (~{math.log2(2*out_swing/lsb):.1f} effective bits)")
    terms, tot, vrms, enbw = noise_budget(d)
    print("-" * 74)
    print(f" Noise budget (input-referred); op-amp {OPAMP['name']}, en = {OPAMP['en_nV']} nV/rtHz")
    for k, v in terms.items():
        print(f"   {k:<40s}{math.sqrt(v)*1e9:7.2f} nV/rtHz")
    print(f"   {'TOTAL':<40s}{tot*1e9:7.2f} nV/rtHz")
    print(f"   Integrated over ENBW {enbw:.0f} Hz: {vrms*1e6:.3f} uV rms in -> {vrms*g*1e6:.1f} uV rms at output "
          f"(~{vrms*g*6.6*1e6:.0f} uV pk-pk)")
    print(f"   Worst-case output offset ({OPAMP['vos_max_mV']} mV Vos x gain {g:.0f}): ~{OPAMP['vos_max_mV']*1e-3*g*1e3:.0f} mV "
          f"-> removed by firmware zero-calibration")
    print("=" * 74)


def monte_carlo(d, n, tol_ina=0.001, tol_rf=0.01, tol_c=0.05, seed=1):
    rng = np.random.default_rng(seed)
    u = lambda nom, tol: nom * (1 + rng.uniform(-tol, tol, n))
    r1a, r1b, rg = u(d["r1"], tol_ina), u(d["r1"], tol_ina), u(d["rg"], tol_ina)
    r2p, r2n = u(d["r2"], tol_ina), u(d["r2"], tol_ina)
    r3p, r3n = u(d["r3"], tol_ina), u(d["r3"], tol_ina)
    gain, cmrr = np.empty(n), np.empty(n)
    for k in range(n):
        res = dict(r1a=r1a[k], r1b=r1b[k], rg=rg[k], r2p=r2p[k], r3p=r3p[k], r2n=r2n[k], r3n=r3n[k])
        gain[k], cmrr[k] = diff_gain(res), cmrr_db(res)
    ra, rb = u(d["rf"], tol_rf), u(d["rf"], tol_rf)
    c1, c2 = u(d["c1"], tol_c), u(d["c2"], tol_c)
    fq = np.array([sk_params(ra[k], rb[k], c1[k], c2[k]) for k in range(n)])
    return gain, cmrr, fq[:, 0], fq[:, 1]


def pct(x, name, unit, fmt="{:.2f}"):
    p1, p50, p99 = np.percentile(x, [1, 50, 99])
    print(f"   {name:<12s} 1%: {fmt.format(p1)} | median: {fmt.format(p50)} | 99%: {fmt.format(p99)} {unit}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mc", type=int, default=0, help="Monte-Carlo trials (e.g. 20000)")
    ap.add_argument("--plot", action="store_true", help="write figures to docs/images/")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "images"))
    a = ap.parse_args()

    d = design()
    report(d)
    mc = None
    if a.mc:
        print(f"\n Monte-Carlo, {a.mc} trials: INA resistors 0.1 %, filter R 1 %, filter C 5 % (uniform)")
        print("   Ideal op-amps: finite op-amp CMRR / GBW / Vos are NOT included.")
        mc = monte_carlo(d, a.mc)
        pct(mc[0], "INA gain", "V/V")
        pct(mc[1], "INA CMRR", "dB (resistor mismatch only)", "{:.1f}")
        pct(mc[2], "Filter f0", "Hz", "{:.0f}")
        pct(mc[3], "Filter Q", "", "{:.3f}")
    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        os.makedirs(a.out, exist_ok=True)
        g = ina_gain(d["r1"], d["rg"], d["r2"], d["r3"])
        f = np.logspace(0, 5, 1000)
        h = g * np.abs(sk_h(f, d["rf"], d["rf"], d["c1"], d["c2"]))
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.semilogx(f, 20 * np.log10(h))
        ax.axvline(f_3db(d["rf"], d["rf"], d["c1"], d["c2"]), ls="--", c="gray", lw=0.8)
        ax.set(xlabel="Frequency (Hz)", ylabel="Gain (dB)", ylim=(-20, 45))
        ax.set_title("Calculated response: INA (x100) + 2nd-order Butterworth, fc ~ 1 kHz (ideal op-amps)", fontsize=9)
        ax.grid(True, which="both", alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(a.out, "calculated_response.png"), dpi=150)
        if mc is not None:
            fig, axs = plt.subplots(1, 3, figsize=(11, 3.2))
            axs[0].hist(mc[0], 50); axs[0].set_title("INA gain (V/V)", fontsize=9)
            axs[1].hist(mc[1], 50); axs[1].set_title("CMRR from resistor mismatch (dB)", fontsize=9)
            axs[2].hist(mc[2], 50); axs[2].set_title("Filter f0 (Hz)", fontsize=9)
            for x in axs:
                x.grid(alpha=0.3)
            fig.suptitle(f"Monte-Carlo ({a.mc} trials, ideal op-amps)", fontsize=9)
            fig.tight_layout(); fig.savefig(os.path.join(a.out, "montecarlo.png"), dpi=150)
        print(f"\n Figures written to {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
