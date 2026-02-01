import curses

# Color Palettes Configuration

# Standard Curses Colors (Base UI)
# ID: (Foreground, Background)
# -1 as background means default terminal background
BASE_PALETTE = {
    1: (curses.COLOR_WHITE, -1),
    2: (curses.COLOR_CYAN, -1),
    3: (curses.COLOR_BLUE, -1),
    4: (curses.COLOR_GREEN, -1),
    5: (curses.COLOR_RED, -1),
    6: (curses.COLOR_YELLOW, -1),
    
    # Custom UI Colors
    20: (86, -1),  # Heatmap 0
    21: (54, -1),  # Heatmap 1
    22: (0, -1),   # Heatmap 2
    23: (149, -1), # Heatmap 3
    24: (223, -1)  # Heatmap 4
}

# Project Colors (IDs 30-39)
# Maps logical index (0-9) to Xterm-256 color codes
# Order: Red, Green, Yellow, Blue, Magenta, Cyan, White, Orange, Lime, Violet
XTERM_256_PALETTE = [
    196, # 0: Red (Bright)
    46,  # 1: Green (Bright)
    226, # 2: Yellow (Bright)
    39,  # 3: Blue (Deep Sky)
    201, # 4: Magenta (Hot Pink)
    51,  # 5: Cyan (Electric)
    231, # 6: White (Bright)
    208, # 7: Orange
    118, # 8: Lime
    129  # 9: Violet
]

# Fallback for limited color terminals
STANDARD_PALETTE = [
    curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_BLUE, 
    curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE, 
    curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_MAGENTA
]

def get_project_color_code(index, can_use_256=True):
    """Returns the color code for a given project index."""
    if can_use_256:
        return XTERM_256_PALETTE[index % len(XTERM_256_PALETTE)]
    return STANDARD_PALETTE[index % len(STANDARD_PALETTE)]
