# display.py — Optional ST7735 1.8" TFT display

import machine

from config import (
    BOARD,
    PIN_DISP_A0,
    PIN_DISP_CS,
    PIN_DISP_RST,
    PIN_DISP_SCK,
    PIN_DISP_SDA,
    USE_DISPLAY,
    VERSION,
)


def init_display():
    if not USE_DISPLAY:
        return None
    try:
        from ST7735 import TFT
        spi = machine.SPI(1, baudrate=20000000, polarity=0, phase=0,
            sck=machine.Pin(PIN_DISP_SCK), mosi=machine.Pin(PIN_DISP_SDA))
        tft = TFT(spi, PIN_DISP_A0, PIN_DISP_RST, PIN_DISP_CS)
        tft.initr()
        tft.rgb(True)
        tft.fill(TFT.BLACK)
        return tft
    except Exception as e:
        print(f"  Display: {e}")
        return None


def display_status(tft, ip, mode, joy_cal, puff_bl, clients):
    if not tft:
        return
    try:
        from ST7735 import TFT
        from sysfont import sysfont
        tft.fill(TFT.BLACK)
        tft.text((5, 5), f"MundMaus v{VERSION}", TFT.WHITE, sysfont)
        tft.text((5, 20), f"{'WLAN' if mode == 'station' else 'HOTSPOT'}: {ip}", TFT.CYAN, sysfont)
        tft.text((5, 35), f"Joy: {joy_cal[0]},{joy_cal[1]}", TFT.GREEN, sysfont)
        tft.text((5, 50), f"Puff: {puff_bl}", TFT.YELLOW, sysfont)
        tft.text((5, 65), f"Clients: {clients}", TFT.WHITE, sysfont)
        tft.text((5, 80), f"{BOARD}", TFT.WHITE, sysfont)
    except:
        pass
