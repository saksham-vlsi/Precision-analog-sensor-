# Firmware - STM32F103C8T6 readout

Reads the front-end output on **PA0 (ADC1_IN0)**, averages 64 samples, converts to input-referred microvolts
and streams CSV over **USART1 (PA9) at 115200 8N1**. The maths lives in `Core/Src/afe.c` (no HAL, unit-tested
on a PC); `app.c` is the thin HAL glue.

## Host unit tests (no hardware)
```
make -C firmware/tests        # builds and runs 13 checks with gcc
```

## Create the CubeIDE project
1. New STM32 project -> `STM32F103C8Tx`. HSE crystal on, clock 72 MHz (HCLK), `PCLK2/6` for ADC = 12 MHz (<= 14 MHz limit).
2. **ADC1**: IN0, continuous off, scan off, 12-bit right-aligned, **sampling time 239.5 cycles** (high-impedance-friendly).
3. **USART1**: asynchronous, 115200, 8N1, PA9 TX / PA10 RX.
4. Generate code, then copy `Core/Inc/afe.h`, `Core/Inc/app.h`, `Core/Src/afe.c`, `Core/Src/app.c` into the project's `Core/`.
5. In `main.c`:
```c
/* USER CODE BEGIN Includes */
#include "app.h"
/* USER CODE END Includes */
...
/* USER CODE BEGIN 2 */
App_Init(&hadc1, &huart1);
/* USER CODE END 2 */
...
while (1) {
  /* USER CODE BEGIN 3 */
  App_Loop();
}
```

## UART commands
| Key | Action |
|---|---|
| `Z` | Zero capture (bridge balanced / inputs shorted) |
| `S` | Span capture (apply +10.000 mV, `APP_CAL_SPAN_UV` in `app.c`) |
| `D` | Restore nominal calibration |

Output: `ms,avg_counts_x100,pin_mV,vin_uV,flags` (flags = 1 when the output is clipping against a rail).
Calibration lives in RAM; storing it in the last flash page is a natural extension.
`APP_VDDA_MV` is set to 3300 - measure your 3V3 rail with the DMM and edit it for best absolute accuracy.

> The firmware was not compiled against the HAL in the environment that generated this repo - only `afe.c` is built and tested on the host. Build `app.c` in CubeIDE and fix any include / handle-name differences.
