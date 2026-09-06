from src.device.display.font import centered_text
from src.device.display.color import color565

BLACK = color565(0, 0, 0)
NAVY = color565(0, 18, 38)
CYAN = color565(0, 210, 255)
WHITE = color565(255, 255, 255)


def splash_screen(display):
    """Render the brief post-init checkpoint through the ILI9341 driver."""
    display.fill(NAVY)
    display.fill_rect(0, 0, display.width, 18, BLACK)
    display.fill_rect(0, display.height - 18, display.width, 18, BLACK)

    top_y = 88
    bottom_y = 160
    centered_text(display, "TFT", top_y, 6, WHITE)
    centered_text(display, "READY", bottom_y, 6, CYAN)
