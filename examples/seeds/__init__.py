"""Hand-authored seed register maps.

These ship inside the wheel so that `pip install regforge` gives you a tool with
parts already in it. Every one is transcribed by hand and marked **unverified**:
machine extraction and human transcription are both starting points, and the
corpus only becomes trustworthy when somebody checks an entry against the
datasheet and runs `regforge verify`.

Adding a part: copy the shape of `bme280.py`, add it to `SEEDS` below, and run
`python examples/seed_corpus.py`. The runner validates every map before writing,
so a transcription slip fails there rather than in somebody's driver.
"""

from __future__ import annotations

from collections.abc import Callable

from regforge.models import DeviceRecord

from . import (
    ads1115,
    adxl345,
    bme280,
    bmp280,
    ds1307,
    ds3231,
    ina219,
    ina226,
    lis3dh,
    mcp23008,
    mcp23017,
    mpu6050,
    pca9685,
)

# Part number -> builder. Kept explicit rather than auto-discovered so that
# adding a part is a visible, reviewable diff.
SEEDS: dict[str, Callable[[], DeviceRecord]] = {
    "ADS1115": ads1115.build_record,
    "ADXL345": adxl345.build_record,
    "BME280": bme280.build_record,
    "BMP280": bmp280.build_record,
    "DS1307": ds1307.build_record,
    "DS3231": ds3231.build_record,
    "INA219": ina219.build_record,
    "INA226": ina226.build_record,
    "LIS3DH": lis3dh.build_record,
    "MCP23008": mcp23008.build_record,
    "MCP23017": mcp23017.build_record,
    "MPU6050": mpu6050.build_record,
    "PCA9685": pca9685.build_record,
}

__all__ = ["SEEDS"]
