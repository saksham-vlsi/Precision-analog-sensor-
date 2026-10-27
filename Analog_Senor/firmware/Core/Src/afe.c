#include "afe.h"

void afe_cal_default(afe_cal_t *cal, float vdda_mV)
{
    /* Output = VDDA/2 + G * Vd, so one count = VDDA/4095 at the pin = that / G at the input. */
    cal->slope_uV_per_count = (vdda_mV * 1000.0f / AFE_ADC_FULL_SCALE) / AFE_GAIN_NOMINAL;
    cal->offset_counts      = AFE_ADC_FULL_SCALE / 2.0f;   /* mid-rail reference */
}

int afe_cal_two_point(afe_cal_t *cal, float counts1, float vin1_uV,
                      float counts2, float vin2_uV)
{
    float dc = counts2 - counts1;
    if (dc > -1.0f && dc < 1.0f) {
        return -1;                                  /* points too close */
    }
    cal->slope_uV_per_count = (vin2_uV - vin1_uV) / dc;
    cal->offset_counts      = counts1 - vin1_uV / cal->slope_uV_per_count;
    return 0;
}

float afe_counts_to_input_uV(const afe_cal_t *cal, float counts)
{
    return (counts - cal->offset_counts) * cal->slope_uV_per_count;
}

float afe_counts_to_pin_mV(float counts, float vdda_mV)
{
    return counts * vdda_mV / AFE_ADC_FULL_SCALE;
}

float afe_average_u16(const uint16_t *samples, uint32_t n)
{
    uint32_t i;
    uint32_t sum = 0;
    if (n == 0u) {
        return 0.0f;
    }
    for (i = 0; i < n; i++) {
        sum += samples[i];
    }
    return (float)sum / (float)n;
}

int afe_is_saturated(float counts)
{
    return (counts < (float)AFE_SAT_LOW_COUNTS) || (counts > (float)AFE_SAT_HIGH_COUNTS);
}
