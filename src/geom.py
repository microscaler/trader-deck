"""Shared dimensions for the PriceWhisperer Deck (mm). PCB top view, +y = back of device."""
PITCH = 19.05
COLX = [-28.575, -9.525, 9.525, 28.575]
ROWY = [28.575, 9.525, -9.525, -34.575]      # row 3 sits 6 mm lower: the safety row
FLAT_X = 21.05                                # 2u FLATTEN key centre

PCB_X0, PCB_X1 = -44.3, 44.3
PCB_Y0, PCB_Y1 = -46.1, 70.5
PCB_R = 2.0
PCB_T = 1.6

ENC = (33.0, 56.0)            # EC11 encoder centre
RING_R = 9.4                  # ring LEDs sit this far above/below the encoder
MCU = (0.0, 58.75)            # RP2040-Zero centre, mounted on the BOTTOM, USB at the back edge
OLED_HDR = (-41.8, 56.0)      # 1x7 wire header for the display, centre

POSTS_PLATE_SCREW = [(-41.3, 19.05), (41.3, 19.05), (-41.3, -12.0), (41.3, -12.0), (-41.3, -43.0)]
POSTS_PLATE_SUPPORT = [(41.3, -43.0)]
POSTS_DECK = [(-40.5, 42.3), (40.5, 42.3), (40.5, 67.5)]
POST_HOLE = 4.3

# key table: name, matrix row, matrix col, x, y, width in units
KEYS = [
    ("BUY MKT", 0, 0), ("BUY ASK", 0, 1), ("SELL BID", 0, 2), ("SELL MKT", 0, 3),
    ("HALF", 1, 0), ("DOUBLE", 1, 1), ("STOP BE", 1, 2), ("TRAIL", 1, 3),
    ("TICK-", 2, 0), ("TICK+", 2, 1), ("TF-", 2, 2), ("TF+", 2, 3),
    ("ARM", 3, 0), ("CANCEL", 3, 1), ("FLATTEN", 3, 3),
]


def key_xy(name, r, c):
    if name == "FLATTEN":
        return FLAT_X, ROWY[3]
    return COLX[c], ROWY[r]
