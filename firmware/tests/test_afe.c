/* Host-side unit tests for afe.c.  Build & run:  make -C firmware/tests */
#include <stdio.h>
#include <math.h>
#include "../Core/Inc/afe.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (!(cond)) { printf("FAIL: %s\n", msg); fails++; } else { printf("ok:   %s\n", msg); } } while (0)
#define NEAR(a, b, tol) (fabsf((a) - (b)) <= (tol))

int main(void)
{
    afe_cal_t c;
    uint16_t s[4] = {100, 102, 98, 100};

    afe_cal_default(&c, 3300.0f);
    CHECK(NEAR(c.slope_uV_per_count, 8.04f, 0.02f), "default slope ~ 8.04 uV/count");
    CHECK(NEAR(c.offset_counts, 2047.5f, 0.01f), "default zero at mid-scale");
    CHECK(NEAR(afe_counts_to_input_uV(&c, 2047.5f), 0.0f, 0.01f), "mid-scale -> 0 uV");
    /* +10 mV in -> pin = 1.65 V + 1.00238 V = 2.65238 V -> 3291.7 counts */
    CHECK(NEAR(afe_counts_to_input_uV(&c, 3291.7f), 10000.0f, 30.0f), "+10 mV full scale maps back to ~10000 uV");
    CHECK(NEAR(afe_counts_to_pin_mV(2047.5f, 3300.0f), 1650.0f, 0.5f), "pin mV at mid-scale");

    /* Simulate a board with offset error and 1.5 % low gain */
    {
        float off = 2100.0f, slope_true = 8.04f / 0.985f;
        float c0 = off, c1 = off + 10000.0f / slope_true;
        CHECK(afe_cal_two_point(&c, c0, 0.0f, c1, 10000.0f) == 0, "two-point accepted");
        CHECK(NEAR(c.offset_counts, off, 0.01f), "two-point offset recovered");
        CHECK(NEAR(afe_counts_to_input_uV(&c, off + 5000.0f / slope_true), 5000.0f, 1.0f), "midpoint reads 5000 uV after cal");
        CHECK(NEAR(afe_counts_to_input_uV(&c, off - 10000.0f / slope_true), -10000.0f, 1.0f), "negative full scale after cal");
    }
    CHECK(afe_cal_two_point(&c, 2000.0f, 0.0f, 2000.4f, 10000.0f) == -1, "rejects identical readings");
    CHECK(NEAR(afe_average_u16(s, 4), 100.0f, 0.001f), "average of samples");
    CHECK(NEAR(afe_average_u16(s, 0), 0.0f, 0.001f), "average with n=0 is 0");
    CHECK(afe_is_saturated(10.0f) && afe_is_saturated(4090.0f) && !afe_is_saturated(2048.0f), "saturation flags");

    printf(fails ? "\n%d test(s) FAILED\n" : "\nall tests passed\n", fails);
    return fails ? 1 : 0;
}
