"""Build a synthetic datasheet PDF for tests.

The page-detection heuristics were tuned against real datasheets but tested
against Python strings, which proves nothing about what happens once pypdf has
extracted the text. This builds a PDF shaped like a real datasheet -- prose
front matter, a register section in the middle, ordering information at the back
-- so the whole load -> score -> select -> slice path runs for real.
"""

from __future__ import annotations

from fpdf import FPDF

PROSE_FRONT = [
    (
        "1. General Description\n\n"
        "The ACME1234 is a combined humidity and pressure sensor designed for mobile "
        "applications where size and low power consumption are decisive design "
        "parameters. The device features excellent long term stability and high "
        "accuracy across the full operating temperature range. It is available in an "
        "extremely compact package suitable for reflow soldering."
    ),
    (
        "2. Features and Benefits\n\n"
        "Small footprint package. Wide supply voltage range. Low current consumption "
        "in sleep mode. Excellent relative accuracy over the operating range. "
        "Suitable for battery powered equipment and wearable devices where the "
        "available board area is severely constrained by the enclosure."
    ),
    (
        "3. Electrical Characteristics\n\n"
        "Supply voltage minimum 1.71 volts, typical 1.8 volts, maximum 3.6 volts. "
        "Sleep current typical 0.1 microamperes. Operating temperature range from "
        "minus forty degrees Celsius to plus eighty five degrees Celsius. "
        "All values are guaranteed by design unless otherwise stated."
    ),
]

REGISTER_PAGES = [
    (
        "5.3 Register Map Overview\n\n"
        "Register  Address   Access   Reset    Description\n"
        "CHIP_ID   0xD0      R/O      0x60     Chip identification number\n"
        "RESET     0xE0      W/O      0x00     Soft reset control\n"
        "CTRL_HUM  0xF2      R/W      0x00     Humidity acquisition options\n"
        "STATUS    0xF3      R/O      0x00     Device status flags\n"
        "CTRL_MEAS 0xF4      R/W      0x00     Measurement control\n"
        "CONFIG    0xF5      R/W      0x00     Rate, filter and interface options\n"
        "\n"
        "Reserved bits must be written as 0. Default values are shown after reset."
    ),
    (
        "5.4 CTRL_MEAS Register (0xF4)\n\n"
        "Bit    Name      Access  Reset  Description\n"
        "[7:5]  osrs_t    R/W     0x0    Temperature oversampling setting\n"
        "[4:2]  osrs_p    R/W     0x0    Pressure oversampling setting\n"
        "[1:0]  mode      R/W     0x0    Sensor operating mode\n"
        "\n"
        "The osrs_t[2:0] field controls oversampling of temperature data. "
        "Bit 7 through bit 5 encode the setting. Reserved values are not permitted."
    ),
    (
        "5.5 CONFIG Register (0xF5)\n\n"
        "Bit    Name      Access  Reset  Description\n"
        "[7:5]  t_sb      R/W     0x0    Inactive duration in normal mode\n"
        "[4:2]  filter    R/W     0x0    IIR filter time constant\n"
        "[1]    reserved  R/O     0x0    Reserved, returns 0\n"
        "[0]    spi3w_en  R/W     0x0    Enable 3-wire SPI interface\n"
        "\n"
        "Writes to the CONFIG register in normal mode are ignored. Address 0xF5."
    ),
    (
        "5.6 STATUS Register (0xF3)\n\n"
        "Bit    Name       Access  Reset  Description\n"
        "[3]    measuring  R/O     0x0    Set while a conversion is running\n"
        "[0]    im_update  R/O     0x0    Set while NVM data is being copied\n"
        "\n"
        "All other bits are reserved and read as 0. Register address 0xF3, reset 0x00."
    ),
]

PROSE_BACK = [
    (
        "7. Package Information\n\n"
        "The device is supplied in a metal lid LGA package. Recommended land pattern "
        "and stencil aperture dimensions are shown in the drawing. Moisture "
        "sensitivity level 1 according to the relevant standard."
    ),
    (
        "8. Ordering Information\n\n"
        "Order code ACME1234 supplied in tape and reel, 3000 units per reel. "
        "Contact your local sales representative for evaluation samples and for "
        "further information regarding lead times and minimum order quantities."
    ),
]


def build_fake_datasheet(path, *, front=None, registers=None, back=None) -> str:
    """Write a multi-page datasheet-shaped PDF. Returns the path as a string.

    Page layout with the defaults: 1-3 prose, 4-7 registers, 8-9 prose.
    """
    front = PROSE_FRONT if front is None else front
    registers = REGISTER_PAGES if registers is None else registers
    back = PROSE_BACK if back is None else back

    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    for block in list(front) + list(registers) + list(back):
        pdf.add_page()
        pdf.set_font("Courier", size=9)
        pdf.multi_cell(w=0, h=4.5, text=block)

    pdf.output(str(path))
    return str(path)


# Zero-based indices of the register pages produced by the defaults.
EXPECTED_REGISTER_PAGES = [3, 4, 5, 6]
FRONT_PAGE_COUNT = len(PROSE_FRONT)
TOTAL_PAGES = len(PROSE_FRONT) + len(REGISTER_PAGES) + len(PROSE_BACK)
