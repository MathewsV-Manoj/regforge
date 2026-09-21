/*
 * Runtime test for an 8-bit part's generated driver, plus the probe path.
 *
 * The 8-bit case matters because the byte-assembly loop is shared with the
 * 16-bit case: at REG_BYTES == 1 it must degenerate to a plain copy rather
 * than shifting anything. A regression there would be invisible in the
 * 16-bit test.
 *
 * Build (CI does this against freshly generated code):
 *     regforge gen BME280 --out ci-out --driver
 *     gcc -std=c99 -Wall -Wextra -Wpedantic -Werror \
 *         -I ci-out tests/c_runtime/bme280_runtime_test.c ci-out/bme280.c -o t && ./t
 */

#include <stdio.h>
#include <string.h>

#include "bme280.h"

static int failures = 0;

#define CHECK(cond)                                                       \
    do {                                                                  \
        if (!(cond)) {                                                    \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);        \
            failures++;                                                   \
        }                                                                 \
    } while (0)

#define CHECK_EQ(actual, expected)                                        \
    do {                                                                  \
        unsigned long a_ = (unsigned long)(actual);                       \
        unsigned long e_ = (unsigned long)(expected);                     \
        if (a_ != e_) {                                                   \
            printf("FAIL %s:%d: %s == 0x%lX, expected 0x%lX\n",           \
                   __FILE__, __LINE__, #actual, a_, e_);                  \
            failures++;                                                   \
        }                                                                 \
    } while (0)

/* ---- fake transport ---------------------------------------------------- */

typedef struct {
    uint8_t store[256];
    int     reads;
    int     writes;
    int     fail_next_read;
} fake_bus_t;

static int fake_read(void *ctx, uint8_t reg, uint8_t *buf, uint16_t len)
{
    fake_bus_t *bus = (fake_bus_t *)ctx;
    uint16_t i;

    if (bus->fail_next_read) {
        bus->fail_next_read = 0;
        return -7;
    }
    for (i = 0; i < len; i++) {
        buf[i] = bus->store[(uint8_t)(reg + i)];
    }
    bus->reads++;
    return 0;
}

static int fake_write(void *ctx, uint8_t reg, const uint8_t *buf, uint16_t len)
{
    fake_bus_t *bus = (fake_bus_t *)ctx;
    uint16_t i;

    for (i = 0; i < len; i++) {
        bus->store[(uint8_t)(reg + i)] = buf[i];
    }
    bus->writes++;
    return 0;
}

/* ---- tests ------------------------------------------------------------- */

int main(void)
{
    fake_bus_t bus;
    bme280_t dev;
    bme280_reg_t value = 0;
    uint8_t burst[6];
    int rc;

    printf("BME280 driver runtime test (REG_BYTES=%u)\n", (unsigned)BME280_REG_BYTES);

    CHECK_EQ(BME280_REG_BYTES, 1u);
    CHECK_EQ(sizeof(bme280_reg_t), 1u);

    memset(&bus, 0, sizeof(bus));
    CHECK_EQ(bme280_init(&dev, fake_read, fake_write, &bus), 0);

    /* Single-byte round trip across the full range: the degenerate path must
     * not shift, mask or truncate anything. */
    {
        unsigned v;
        for (v = 0; v <= 0xFFu; v++) {
            bme280_reg_t got = 0;
            CHECK_EQ(bme280_write_reg(&dev, BME280_CTRL_MEAS, (bme280_reg_t)v), 0);
            CHECK_EQ(bme280_read_reg(&dev, BME280_CTRL_MEAS, &got), 0);
            if (got != (bme280_reg_t)v) {
                CHECK_EQ(got, v);
                break;
            }
        }
    }

    /* probe() must accept the documented chip ID and reject anything else. */
    bus.store[BME280_CHIP_ID] = BME280_CHIP_ID_RESET;
    CHECK_EQ(bme280_probe(&dev), 0);

    bus.store[BME280_CHIP_ID] = 0x58u; /* a BMP280 on the same bus address */
    CHECK_EQ(bme280_probe(&dev), -2);

    bus.store[BME280_CHIP_ID] = BME280_CHIP_ID_RESET;
    bus.fail_next_read = 1;
    CHECK_EQ(bme280_probe(&dev), -1);

    /* Field macros compose with the driver. */
    memset(&bus, 0, sizeof(bus));
    bme280_init(&dev, fake_read, fake_write, &bus);
    {
        bme280_reg_t ctrl = 0;
        ctrl = BME280_CTRL_MEAS_OSRS_T_SET(ctrl, BME280_CTRL_MEAS_OSRS_T_X2);
        ctrl = BME280_CTRL_MEAS_MODE_SET(ctrl, BME280_CTRL_MEAS_MODE_NORMAL);
        CHECK_EQ(bme280_write_reg(&dev, BME280_CTRL_MEAS, ctrl), 0);

        CHECK_EQ(bme280_read_reg(&dev, BME280_CTRL_MEAS, &value), 0);
        CHECK_EQ(BME280_CTRL_MEAS_OSRS_T_GET(value), BME280_CTRL_MEAS_OSRS_T_X2);
        CHECK_EQ(BME280_CTRL_MEAS_MODE_GET(value), BME280_CTRL_MEAS_MODE_NORMAL);
        /* Setting one field must not disturb the other. */
        CHECK_EQ(value, (bme280_reg_t)(0x40u | 0x03u));
    }

    /* Read-modify-write preserves neighbouring fields. */
    CHECK_EQ(bme280_write_reg(&dev, BME280_CONFIG, 0xFFu), 0);
    CHECK_EQ(bme280_update_bits(&dev, BME280_CONFIG, BME280_CONFIG_FILTER_MASK, 0), 0);
    CHECK_EQ(bme280_read_reg(&dev, BME280_CONFIG, &value), 0);
    CHECK_EQ(value, (bme280_reg_t)(0xFFu & ~BME280_CONFIG_FILTER_MASK));

    {
        int writes_before = bus.writes;
        CHECK_EQ(bme280_update_bits(&dev, BME280_CONFIG, BME280_CONFIG_FILTER_MASK, 0), 0);
        CHECK_EQ(bus.writes, writes_before);
    }

    /* Burst reads are what measurement output actually uses. */
    memset(&bus, 0, sizeof(bus));
    bme280_init(&dev, fake_read, fake_write, &bus);
    bus.store[BME280_PRESS_MSB]  = 0x11u;
    bus.store[BME280_PRESS_LSB]  = 0x22u;
    bus.store[BME280_PRESS_XLSB] = 0x33u;
    memset(burst, 0, sizeof(burst));
    CHECK_EQ(bme280_read_burst(&dev, BME280_PRESS_MSB, burst, 3u), 0);
    CHECK_EQ(burst[0], 0x11u);
    CHECK_EQ(burst[1], 0x22u);
    CHECK_EQ(burst[2], 0x33u);

    CHECK(bme280_read_burst(&dev, BME280_PRESS_MSB, NULL, 3u) != 0);
    bus.fail_next_read = 1;
    rc = bme280_read_burst(&dev, BME280_PRESS_MSB, burst, 3u);
    CHECK(rc != 0);

    if (failures == 0) {
        printf("PASS: BME280 driver runtime test\n");
        return 0;
    }
    printf("FAILED: %d check(s)\n", failures);
    return 1;
}
