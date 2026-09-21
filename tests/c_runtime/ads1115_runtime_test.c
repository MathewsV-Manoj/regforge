/*
 * Runtime test for a 16-bit part's generated driver.
 *
 * The generated self-check proves the *macros* are right at compile time. It
 * cannot prove the *driver* is right, because byte assembly is runtime logic:
 * whether read_reg reassembles two bytes into 0x8583 in the correct order only
 * shows up when the code runs.
 *
 * This links the generated driver against a fake transport that records every
 * byte, so the assembly is checked for real. It is the test that would have
 * caught the driver emitting a uint8_t accessor for a 16-bit register.
 *
 * Build (CI does this against freshly generated code):
 *     regforge gen ADS1115 --out ci-out --driver
 *     gcc -std=c99 -Wall -Wextra -Wpedantic -Werror \
 *         -I ci-out tests/c_runtime/ads1115_runtime_test.c ci-out/ads1115.c -o t && ./t
 */

#include <stdio.h>
#include <string.h>

#include "ads1115.h"

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

#define FAKE_REGS 8
#define FAKE_MAX  4

typedef struct {
    uint8_t  store[FAKE_REGS][FAKE_MAX];
    uint8_t  last_write[FAKE_MAX];
    uint16_t last_write_len;
    uint8_t  last_reg;
    int      reads;
    int      writes;
    int      fail_next_read;
} fake_bus_t;

static int fake_read(void *ctx, uint8_t reg, uint8_t *buf, uint16_t len)
{
    fake_bus_t *bus = (fake_bus_t *)ctx;
    if (bus->fail_next_read) {
        bus->fail_next_read = 0;
        return -7;
    }
    if (reg >= FAKE_REGS || len > FAKE_MAX) {
        return -1;
    }
    memcpy(buf, bus->store[reg], len);
    bus->last_reg = reg;
    bus->reads++;
    return 0;
}

static int fake_write(void *ctx, uint8_t reg, const uint8_t *buf, uint16_t len)
{
    fake_bus_t *bus = (fake_bus_t *)ctx;
    if (reg >= FAKE_REGS || len > FAKE_MAX) {
        return -1;
    }
    memcpy(bus->store[reg], buf, len);
    memcpy(bus->last_write, buf, len);
    bus->last_write_len = len;
    bus->last_reg = reg;
    bus->writes++;
    return 0;
}

static void reset_bus(fake_bus_t *bus)
{
    memset(bus, 0, sizeof(*bus));
}

/* ---- tests ------------------------------------------------------------- */

int main(void)
{
    fake_bus_t bus;
    ads1115_t dev;
    ads1115_reg_t value = 0;
    int rc;

    printf("ADS1115 driver runtime test (REG_BYTES=%u)\n", (unsigned)ADS1115_REG_BYTES);

    /* The whole point: a 16-bit part must move two bytes per register. */
    CHECK_EQ(ADS1115_REG_BYTES, 2u);
    CHECK_EQ(sizeof(ads1115_reg_t), 2u);

    reset_bus(&bus);
    CHECK_EQ(ads1115_init(&dev, fake_read, fake_write, &bus), 0);

    /* NULL arguments are rejected rather than dereferenced. */
    CHECK(ads1115_init(NULL, fake_read, fake_write, &bus) != 0);
    CHECK(ads1115_init(&dev, NULL, fake_write, &bus) != 0);
    CHECK(ads1115_init(&dev, fake_read, NULL, &bus) != 0);
    CHECK(ads1115_read_reg(&dev, ADS1115_CONFIG, NULL) != 0);

    /* Write the documented reset value and check the byte order on the wire.
     * MSB first by default, so 0x8583 must go out as {0x85, 0x83}. */
    reset_bus(&bus);
    ads1115_init(&dev, fake_read, fake_write, &bus);
    CHECK_EQ(ads1115_write_reg(&dev, ADS1115_CONFIG, 0x8583u), 0);
    CHECK_EQ(bus.last_write_len, 2u);
    CHECK_EQ(bus.last_write[0], 0x85u);
    CHECK_EQ(bus.last_write[1], 0x83u);

    /* ...and that reading it back reassembles the same value. */
    CHECK_EQ(ads1115_read_reg(&dev, ADS1115_CONFIG, &value), 0);
    CHECK_EQ(value, 0x8583u);

    /* Round-trip a spread of values, including ones that would survive a
     * byte swap unnoticed if we only tested palindromes. */
    {
        static const ads1115_reg_t cases[] = {
            0x0000u, 0x0001u, 0x00FFu, 0x0100u, 0x1234u, 0x8000u, 0xFF00u, 0xFFFFu, 0x8583u,
        };
        size_t i;
        for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
            ads1115_reg_t got = 0;
            CHECK_EQ(ads1115_write_reg(&dev, ADS1115_LO_THRESH, cases[i]), 0);
            CHECK_EQ(ads1115_read_reg(&dev, ADS1115_LO_THRESH, &got), 0);
            CHECK_EQ(got, cases[i]);
        }
    }

    /* Field macros must compose with the driver, not just with themselves. */
    reset_bus(&bus);
    ads1115_init(&dev, fake_read, fake_write, &bus);
    {
        ads1115_reg_t cfg = 0;
        cfg = ADS1115_CONFIG_MUX_SET(cfg, ADS1115_CONFIG_MUX_AIN0_GND);
        cfg = ADS1115_CONFIG_PGA_SET(cfg, ADS1115_CONFIG_PGA_FSR_1_024V);
        cfg = ADS1115_CONFIG_MODE_SET(cfg, ADS1115_CONFIG_MODE_CONTINUOUS);
        CHECK_EQ(ads1115_write_reg(&dev, ADS1115_CONFIG, cfg), 0);

        CHECK_EQ(ads1115_read_reg(&dev, ADS1115_CONFIG, &value), 0);
        CHECK_EQ(ADS1115_CONFIG_MUX_GET(value), ADS1115_CONFIG_MUX_AIN0_GND);
        CHECK_EQ(ADS1115_CONFIG_PGA_GET(value), ADS1115_CONFIG_PGA_FSR_1_024V);
        CHECK_EQ(ADS1115_CONFIG_MODE_GET(value), ADS1115_CONFIG_MODE_CONTINUOUS);
    }

    /* update_bits must be a true read-modify-write: change the masked field,
     * leave everything else exactly as it was. */
    reset_bus(&bus);
    ads1115_init(&dev, fake_read, fake_write, &bus);
    CHECK_EQ(ads1115_write_reg(&dev, ADS1115_CONFIG, 0xFFFFu), 0);
    CHECK_EQ(ads1115_update_bits(&dev, ADS1115_CONFIG, ADS1115_CONFIG_DR_MASK, 0), 0);
    CHECK_EQ(ads1115_read_reg(&dev, ADS1115_CONFIG, &value), 0);
    CHECK_EQ(value, (ads1115_reg_t)(0xFFFFu & ~ADS1115_CONFIG_DR_MASK));

    /* A no-op update must not touch the bus at all. */
    {
        int writes_before = bus.writes;
        CHECK_EQ(ads1115_update_bits(&dev, ADS1115_CONFIG, ADS1115_CONFIG_DR_MASK, 0), 0);
        CHECK_EQ(bus.writes, writes_before);
    }

    /* Transport errors propagate instead of being swallowed. */
    bus.fail_next_read = 1;
    rc = ads1115_read_reg(&dev, ADS1115_CONFIG, &value);
    CHECK(rc != 0);

    bus.fail_next_read = 1;
    rc = ads1115_update_bits(&dev, ADS1115_CONFIG, ADS1115_CONFIG_DR_MASK, 0);
    CHECK(rc != 0);

    if (failures == 0) {
        printf("PASS: ADS1115 driver runtime test\n");
        return 0;
    }
    printf("FAILED: %d check(s)\n", failures);
    return 1;
}
