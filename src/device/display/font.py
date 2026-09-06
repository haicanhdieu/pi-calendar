FONT_5X7 = {
    " ": (
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
    ),
    "?": (
        "01110",
        "10001",
        "00001",
        "00010",
        "00100",
        "00000",
        "00100",
    ),
    "D": (
        "11110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "11110",
    ),
    "E": (
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "11111",
    ),
    "F": (
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "10000",
    ),
    "H": (
        "10001",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ),
    "I": (
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "11111",
    ),
    "K": (
        "10001",
        "10010",
        "10100",
        "11000",
        "10100",
        "10010",
        "10001",
    ),
    "L": (
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "11111",
    ),
    "O": (
        "01110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ),
    "P": (
        "11110",
        "10001",
        "10001",
        "11110",
        "10000",
        "10000",
        "10000",
    ),
    "R": (
        "11110",
        "10001",
        "10001",
        "11110",
        "10100",
        "10010",
        "10001",
    ),
    "T": (
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
    ),
    "W": (
        "10001",
        "10001",
        "10001",
        "10101",
        "10101",
        "10101",
        "01010",
    ),
}


def draw_glyph(display, x, y, char, scale, color):
    bitmap = FONT_5X7.get(char, FONT_5X7["?"])
    for row_index, row_bits in enumerate(bitmap):
        py = y + (row_index * scale)
        for col_index, bit in enumerate(row_bits):
            if bit == "1":
                display.fill_rect(
                    x + (col_index * scale),
                    py,
                    scale,
                    scale,
                    color,
                )


def draw_text(display, text, x, y, scale, color):
    cursor_x = x
    step = 6 * scale
    for char in text:
        if char == "\n":
            y += 8 * scale
            cursor_x = x
            continue
        draw_glyph(display, cursor_x, y, char.upper(), scale, color)
        cursor_x += step


def text_width(text, scale):
    if not text:
        return 0
    return (len(text) * 6 - 1) * scale


def centered_text(display, text, y, scale, color):
    x = (display.width - text_width(text, scale)) // 2
    draw_text(display, text, x, y, scale, color)
