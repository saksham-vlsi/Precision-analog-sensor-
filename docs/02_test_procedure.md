# 02 - Bench test procedure

Record every result in `measurements/*.csv`, then run `scripts/analyze_bench.py`. Add the plots and
photos to `docs/images/` and the summary numbers to the README results table. **Only publish numbers you measured.**

Equipment: DMM (4.5 digits+), oscilloscope (>= 50 MHz, 10x probe, BW-limit on), function generator, 3.3 V supply
(or the Blue Pill 3V3), Fixtures A and B (see `03_build_guide.md`).

## T0 - Power-on checks (before connecting any signal)
1. Supply current: expect a few mA (quad + dual CMOS op-amps and dividers). Anything > 20 mA -> stop, check wiring.
2. `vref` = 1.650 V +/- 5 mV. Output `adc` with inputs at Vref: within ~0.2 V of 1.65 V (offset x100).
3. Scope the output with inputs shorted: no oscillation (look at 10 mV/div, 1 ms/div and 20 us/div).

## T1 - DC gain, offset, linearity (Fixture A)
1. Adjust the trimmer from -10 mV to +10 mV in 2 mV steps (11 points, and again in reverse for hysteresis/settling).
2. At each point log `vin_mV` (DMM across bridge) and `vout_V` (DMM at `adc`) in `measurements/gain_sweep.csv`.
3. `python scripts/analyze_bench.py gain measurements/gain_sweep.csv --plot`
Reports gain error vs 100.238 V/V, output offset, input-referred offset, linearity (% of span).

## T2 - Frequency response (Fixture B)
1. 20 mVpp at the INA input, sweep 10 Hz ... 20 kHz (about 5 points/decade, denser around 1 kHz).
2. Log `freq_Hz, vin_mVpp, vout_mVpp` (use the scope's pk-pk or RMS measurement consistently).
3. `python scripts/analyze_bench.py freq measurements/freq_response.csv --plot`
Compare -3 dB (simulation 977 Hz) and roll-off (-40 dB/decade above the corner).

## T3 - Step response
Square wave 2 Vpp / 100 Hz, offset 1.65 V through Fixture B. Capture rise time (10-90 %) and overshoot;
compare with the ngspice plot (`docs/images/sim_step.png`, ~4 % overshoot).

## T4 - CMRR
1. Tie IN+ and IN- together, drive 1 Vpp sine centred on 1.65 V at 50 Hz, 100 Hz, 1 kHz.
2. Log `freq_Hz, vcm_Vpp, vout_mVpp` -> `analyze_bench.py cmrr ... --gain <measured gain>`.
3. If the output is below the scope noise floor, report CMRR as "> X dB" (lower bound), not as a measured value.

## T5 - Output noise
Inputs tied to Vref through 500 ohm each, AC-coupled scope, 20 MHz BW limit, 10k+ samples exported.
`analyze_bench.py noise measurements/noise_scope.csv`. Short the scope probe once and capture its own noise floor:
if your reading is within ~2x of that floor it is an upper bound only. (The 12-bit ADC cannot resolve it: 1 LSB = 806 uV.)

## T6 - ADC read-back accuracy (firmware)
1. Flash the firmware, open a serial terminal at 115200.
2. Balance the bridge, send `Z`; set +10.000 mV (DMM), send `S`.
3. Step through the range; log `applied_uV` (DMM) vs `reported_uV` (CSV `vin_uV`) -> `analyze_bench.py adc ...`.

## T7 - Monte-Carlo vs reality (optional)
Build 3-5 units with different resistor draws (or swap Rg between 1.05 k +/-0.1 %) and compare spread with the Monte-Carlo prediction.
