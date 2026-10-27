/**
 * app.c - Reads the front-end output on PA0 (ADC1_IN0), averages, converts and
 *         streams CSV over USART1 (115200 8N1).
 *
 * UART commands (single character, no newline needed):
 *   'Z'  zero-point capture : inputs shorted / bridge balanced (0 uV differential)
 *   'S'  span-point capture : apply APP_CAL_SPAN_UV at the input, then send 'S'
 *   'D'  restore nominal (design-equation) calibration
 *
 * CSV line: ms,avg_counts_x100,pin_mV,vin_uV,flags
 *   flags: 0 = OK, 1 = output clipping against a rail
 * Integer formatting only, so no -u _printf_float linker flag is needed.
 */
#include "app.h"
#include "afe.h"
#include <stdio.h>

#define APP_OVERSAMPLE     64u        /* 64 samples -> ~+3 bit if noise >= 1 LSB (dither) */
#define APP_PERIOD_MS      100u
#define APP_VDDA_MV        3300.0f    /* measure your 3V3 rail with a DMM and edit        */
#define APP_CAL_SPAN_UV    10000.0f   /* +10.000 mV differential used for 'S'             */

static ADC_HandleTypeDef  *s_adc;
static UART_HandleTypeDef *s_uart;
static afe_cal_t           s_cal;
static float               s_zero_counts;
static int                 s_have_zero;
static uint32_t            s_next_ms;

static uint16_t read_adc_once(void)
{
    HAL_ADC_Start(s_adc);
    HAL_ADC_PollForConversion(s_adc, 10);
    return (uint16_t)HAL_ADC_GetValue(s_adc);
}

static float read_adc_avg(void)
{
    uint16_t buf[APP_OVERSAMPLE];
    uint32_t i;
    for (i = 0; i < APP_OVERSAMPLE; i++) {
        buf[i] = read_adc_once();
    }
    return afe_average_u16(buf, APP_OVERSAMPLE);
}

static void uart_puts(const char *s)
{
    uint16_t n = 0;
    while (s[n] != '\0') { n++; }
    HAL_UART_Transmit(s_uart, (uint8_t *)s, n, 100);
}

static void handle_command(char c, float avg)
{
    char msg[64];
    switch (c) {
    case 'Z':
        s_zero_counts = avg;
        s_have_zero   = 1;
        s_cal.offset_counts = avg;                 /* keeps nominal slope until 'S' */
        snprintf(msg, sizeof msg, "# zero captured: %ld counts x100\r\n", (long)(avg * 100.0f));
        uart_puts(msg);
        break;
    case 'S':
        if (s_have_zero && afe_cal_two_point(&s_cal, s_zero_counts, 0.0f, avg, APP_CAL_SPAN_UV) == 0) {
            snprintf(msg, sizeof msg, "# span captured: slope %ld nV/count\r\n",
                     (long)(s_cal.slope_uV_per_count * 1000.0f));
        } else {
            snprintf(msg, sizeof msg, "# span rejected: send 'Z' first / points too close\r\n");
        }
        uart_puts(msg);
        break;
    case 'D':
        afe_cal_default(&s_cal, APP_VDDA_MV);
        s_have_zero = 0;
        uart_puts("# nominal calibration restored\r\n");
        break;
    default:
        break;
    }
}

void App_Init(ADC_HandleTypeDef *hadc, UART_HandleTypeDef *huart)
{
    s_adc  = hadc;
    s_uart = huart;
    HAL_ADCEx_Calibration_Start(s_adc);            /* STM32F1 internal ADC self-calibration */
    afe_cal_default(&s_cal, APP_VDDA_MV);
    s_next_ms = HAL_GetTick();
    uart_puts("# Precision Analog Sensor Front-End - STM32F103 readout\r\n");
    uart_puts("# ms,avg_counts_x100,pin_mV,vin_uV,flags   (Z=zero, S=span, D=default)\r\n");
}

void App_Loop(void)
{
    uint8_t  rx;
    char     line[96];
    float    avg;
    uint32_t now = HAL_GetTick();

    if ((int32_t)(now - s_next_ms) < 0) {
        return;
    }
    s_next_ms = now + APP_PERIOD_MS;

    avg = read_adc_avg();

    if (HAL_UART_Receive(s_uart, &rx, 1, 0) == HAL_OK) {
        handle_command((char)rx, avg);
    }

    snprintf(line, sizeof line, "%lu,%ld,%ld,%ld,%d\r\n",
             (unsigned long)now,
             (long)(avg * 100.0f),
             (long)afe_counts_to_pin_mV(avg, APP_VDDA_MV),
             (long)afe_counts_to_input_uV(&s_cal, avg),
             afe_is_saturated(avg));
    uart_puts(line);
}
