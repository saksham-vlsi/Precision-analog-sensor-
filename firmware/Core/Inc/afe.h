/**
 * afe.h - Hardware-independent maths for the Precision Analog Sensor Front-End.
 *
 * Converts STM32 12-bit ADC counts to the bridge's input-referred differential
 * voltage, with default (nominal) and two-point (measured) calibration.
 * No HAL dependency, so it can be unit-tested on a PC (see firmware/tests).
 */
#ifndef AFE_H
#define AFE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define AFE_ADC_FULL_SCALE   4095.0f   /* 12-bit ADC                               */
#define AFE_GAIN_NOMINAL     100.238f  /* (1 + 2*R1/Rg) * R3/R2 = 20.048 * 5       */
#define AFE_SAT_LOW_COUNTS   40u       /* output within ~32 mV of GND -> clipped   */
#define AFE_SAT_HIGH_COUNTS  4055u     /* output within ~32 mV of VDD -> clipped   */

typedef struct {
    float slope_uV_per_count;  /* input-referred microvolts per ADC count          */
    float offset_counts;       /* ADC count that corresponds to 0 V differential   */
} afe_cal_t;

/** Nominal calibration from the design equations (ratiometric: ADC ref = VDDA). */
void afe_cal_default(afe_cal_t *cal, float vdda_mV);

/**
 * Two-point calibration from two known differential inputs (e.g. 0 uV and
 * +10000 uV from the bench bridge).  Returns 0 on success, -1 if the two
 * ADC readings are too close to define a slope.
 */
int afe_cal_two_point(afe_cal_t *cal, float counts1, float vin1_uV,
                      float counts2, float vin2_uV);

/** Counts -> input-referred differential voltage in microvolts. */
float afe_counts_to_input_uV(const afe_cal_t *cal, float counts);

/** Counts -> voltage at the ADC pin in millivolts (for debugging the analog chain). */
float afe_counts_to_pin_mV(float counts, float vdda_mV);

/** Average of n 16-bit samples (oversampling / decimation). Returns 0 if n == 0. */
float afe_average_u16(const uint16_t *samples, uint32_t n);

/** Non-zero if the average count indicates the output is clipping against a rail. */
int afe_is_saturated(float counts);

#ifdef __cplusplus
}
#endif
#endif /* AFE_H */
