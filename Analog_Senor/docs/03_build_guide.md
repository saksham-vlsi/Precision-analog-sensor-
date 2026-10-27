# 03 - Build guide

## Connection table (matches `simulation/ina_filter_full.cir`)

Power: 3.3 V from the Blue Pill `3V3` pin (or a clean bench supply with common ground). Bypass every op-amp
package with 100 nF at the pins + one 10 uF bulk cap on the rail.

| Net | From | To |
|---|---|---|
| `vref` (1.65 V) | Rd1/Rd2 divider midpoint -> A4(+) ; A4 output tied to A4(-) | A3 reference resistor R3p, test fixtures |
| `inp` / `inn` | Bridge+ / Bridge- through Rfp / Rfn (1 k) | A1(+) / A2(+) ; Cdif (10 n) between them ; Ccp / Ccn (1 n) to GND |
| A1 | (+)=`inp`, (-)=`a1n`, out=`o1` | R1a `o1`-`a1n` |
| A2 | (+)=`inn`, (-)=`a2n`, out=`o2` | R1b `o2`-`a2n` |
| Gain resistor | Rg (1.05 k) between `a1n` and `a2n` | |
| A3 (difference amp) | (+)=`a3p`, (-)=`a3n`, out=`o3` | R2p `o1`-`a3p`, R3p `a3p`-`vref`, R2n `o2`-`a3n`, R3n `o3`-`a3n` |
| Sallen-Key (U2A) | `o3` -> Rs1 -> `skx` -> Rs2 -> `sky` = U2A(+) ; Cs2 `sky`-GND ; Cs1 `skx`-`o5` ; U2A(-) = `o5` = output | |
| ADC | `o5` -> Radc (100) -> `adc` -> Blue Pill **PA0** ; Cadc (10 n) `adc`-GND | |
| Serial | Blue Pill **PA9 (USART1 TX)** -> USB-UART RX ; GND common | |
| Unused U2B | (+) to `vref`, (-) to output (follower) | |

Op-amp pin-outs differ by package - take them from the TLV9064 / TLV9062 datasheets (TI product pages).

## Layout rules that decide whether you reach the predicted CMRR

1. Keep the **INA input traces short and symmetric**; route the two inputs side by side (twisted pair off-board).
2. Match `R1a/R1b`, `R2p/R2n`, `R3p/R3n` - use the same batch of 0.1 % parts, lay them out identically.
3. Put the 100 nF bypass caps **on the supply pins**, not at the end of the board.
4. Keep the Sallen-Key capacitors away from the digital lines (PA9 TX edges couple into the 100k-class nodes).
5. Single ground point (star) between analog return and MCU ground.
6. Use film/C0G caps in the filter; solderless breadboards add ~2-5 pF per node and leakage - perfboard is better.

## Test fixtures

### Fixture A - bridge emulator (DC tests)
```
3V3 --[1k 0.1%]--+--[1k 0.1%]-- GND            left leg  -> Bridge-  (1.650 V)
3V3 --[1k 0.1%]--[ 20 ohm 10-turn trimmer ]--[1k 0.1%]-- GND
                      wiper -> Bridge+                right leg -> Bridge+ (1.571 ... 1.729 V span)
```
Wiper voltage swings by about +/-16 mV around 1.65 V, so +/-10 mV is reachable with the trimmer.
Measure the differential voltage across `Bridge+` / `Bridge-` with the DMM (4.5-digit or better on the 100 mV range),
and the output at `adc` with the same DMM.

### Fixture B - AC injection (frequency, step, CMRR)
```
Function generator --[990 ohm]--+--> IN+ (via the board's Rfp)
                                |
                             [10 ohm]
                                |
                               Vref (1.65 V, buffered)        IN- = Vref
```
The 100:1 divider turns a 2 Vpp generator output (set the DC offset to 1.65 V and hi-Z load) into
20 mVpp at the INA. Common ground between generator, scope and board.

For **CMRR**, tie IN+ and IN- together and drive both from the generator through 100 ohm (offset 1.65 V,
1 Vpp). Any output you see is common-mode leakage.

## Firmware

See `firmware/README.md`.
