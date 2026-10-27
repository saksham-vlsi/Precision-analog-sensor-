# 01 - Design calculations

Reproduce every number here with `python scripts/design_calc.py --mc 20000 --plot`.

## 1. Requirements

| Item | Value | Why |
|---|---|---|
| Supply | 3.3 V single | Same rail as the STM32 ADC reference -> ratiometric measurement |
| Sensor | Resistive bridge, +/-10 mV full-scale differential, 1.65 V common-mode | Typical load-cell / strain-gauge / NTC-bridge level |
| Total gain | 100 V/V | +/-10 mV -> +/-1.0 V around mid-rail: 0.65 V ... 2.65 V, clear of both rails |
| Signal band | DC ... ~1 kHz | Slow sensor; anti-alias for a low-rate ADC |
| Filter | 2nd-order Butterworth low-pass | Maximally flat passband, no peaking |
| CMRR target | > 80 dB at low frequency | Bridge common-mode is 1.65 V while the signal is 10 mV |

## 2. Topology

See the block diagram in the main README. (Exact connectivity: `simulation/ina_filter_full.cir`, and the pin table in `03_build_guide.md`.)

Stage 1 (A1, A2): `G1 = 1 + 2*R1/Rg`, common-mode gain = 1.
Stage 2 (A3): `G2 = R3/R2`, referenced to Vref (1.65 V) so the output sits at mid-rail.

**Why put most of the gain in stage 1?** Resistor mismatch in the difference amplifier sets the
CMRR of stage 2 only; stage 1 passes common-mode at unity gain but amplifies the differential
signal by G1, so the total CMRR improves by about `G1` (here x20 = +26 dB).

## 3. INA gain resistors

```
G_total = 100 = G1 * G2,   G2 = 5  ->  G1 = 20
Rg = 2*R1 / (G1 - 1) = 2 * 10k / 19 = 1052.6 ohm  ->  nearest E96 = 1.05 k
G1 = 1 + 20k / 1.05k = 20.048
G2 = 100k / 20k = 5.000          (R2 = 20 k, R3 = 100 k)
G  = 100.238 V/V = 40.02 dB
```
Output at full scale: `1.65 V +/- 100.238 * 10 mV = 0.648 V ... 2.652 V`.

## 4. Sallen-Key low-pass (unity gain)

```
H(s) = 1 / ( s^2 R1R2 C1C2 + s C2 (R1+R2) + 1 )
f0   = 1 / (2*pi*sqrt(R1 R2 C1 C2)),    Q = sqrt(R1 R2 C1 C2) / ( C2 (R1+R2) )
```
With `R1 = R2 = R` : `Q = 0.5 * sqrt(C1/C2)`. Butterworth needs `Q = 1/sqrt(2)` -> `C1 = 2*C2`.

```
C2 = 10 nF,  C1 = 20 nF (2 x 10 nF in parallel)
R  = 1 / (2*pi * 1 kHz * C2 * sqrt(2)) = 11.25 k  ->  E96 = 11.3 k
f0 = 995.9 Hz,  Q = 0.7071
```
C0G/NP0 or film capacitors are required: X7R changes capacitance with DC bias and temperature,
which moves `f0` and `Q` (and adds distortion).

## 5. Input network (RFI / protection)

`Rf = 1 k` in each leg, `Cdif = 10 nF` across the inputs, `Ccm = 1 nF` from each input to ground.
Differential corner `~ 1 / (2*pi * 2*(Rf + Rs) * (Cdif + Ccm/2))` ~ 7 kHz, so it sits a decade
above the 1 kHz signal filter but removes RF pickup. Keep `Cdif >= 10 x Ccm`: any mismatch
between the two `Ccm` caps converts common-mode into differential error, and the larger
`Cdif` swamps it.

## 6. ADC interface

STM32F103: 12-bit, `VDDA = 3.3 V` -> `1 LSB = 0.806 mV` at the pin = `8.04 uV` input-referred.
+/-10 mV spans about 2488 counts (~11.3 bit). `Radc = 100 ohm` + `Cadc = 10 nF` supplies the
sample-and-hold charge so the op-amp is not hit by the sampling kick-back. Averaging 64 samples
reduces noise by 8x *when the noise is larger than one LSB* (it is not here - see the noise
section - so extra resolution from oversampling is limited; a quieter ADC or more gain would be
needed to exploit the front-end noise floor).

## 7. Predicted performance (ideal op-amps unless stated)

| Metric | Prediction | Source |
|---|---|---|
| Gain | 100.24 V/V, spread 100.01 ... 100.46 V/V (1 %-99 %) with 0.1 % resistors | Python Monte-Carlo |
| -3 dB frequency | 996 Hz ideal; **977 Hz** in simulation (input RFI filter pulls it down ~2 %) | Python / ngspice |
| Filter f0 spread | 953 ... 1042 Hz with 1 % R and 5 % C | Python Monte-Carlo |
| Q spread | 0.68 ... 0.74 (mild peaking possible) | Python Monte-Carlo |
| CMRR (resistor mismatch only) | median ~103 dB, 1 % of units below ~92 dB | Python Monte-Carlo |
| Step overshoot | ~4.3 % of step (2.737 V peak for 2.652 V final) | ngspice |
| Input-referred noise | ~16.7 nV/rtHz -> ~0.56 uV rms in 1.1 kHz -> ~56 uV rms at output | `design_calc.py` (assumes en = 10 nV/rtHz) |
| Worst-case output offset | up to ~160 mV for 1.6 mV Vos x 100 | removed by firmware zero calibration |

**Real CMRR will be lower** than the table: it is further limited by the op-amps' own CMRR,
by PCB / breadboard leakage and by the RFI-cap mismatch. Treat 103 dB as a ceiling, and report
the number you *measure*.

## 8. Error budget (what to expect on the bench)

| Source | Effect | Fix |
|---|---|---|
| Op-amp Vos x G | Output offset up to ~100 mV+ | Firmware zero point ('Z' command) |
| Rg tolerance 0.1 % | ~0.1 % gain | Two-point (span) calibration |
| Bridge excitation drift | Ratiometric - cancels because the ADC ref is the same 3.3 V | Keep excitation and VDDA on one rail |
| Breadboard parasitics | Hum pickup, reduced CMRR | Short leads, perfboard + ground pour, twisted pair to sensor |
| 1/f noise (CMOS op-amp) | Not in the white-noise budget | Datasheet 0.1-10 Hz noise; chopper op-amp if DC accuracy matters |

## 9. Next step: chopper / zero-drift variant

If low-frequency offset and drift dominate, swap the INA amplifiers for zero-drift types (e.g. the TI OPAx333 family). Check the datasheet first and re-run `design_calc.py` with the new `OPAMP` values.
