import os

# --- Configuration & Constants ---
DATA_FILE = "timer_history.json"
TODO_FILE = "todo_data.json"
CONFIG_FILE = "timer_config.json"
PRESETS = [5, 10, 15, 20, 25, 30, 45, 60, 90, 120]

DEFAULT_CONFIG = {
    "project_tags": {},
    "classes": [
        {"name": "Code Wizard", "tags": ["code", "py", "dev", "script", "backend"]},
        {"name": "Data Ronin", "tags": ["data", "sql", "analysis", "pandas", "ai"]},
        {"name": "SysAdmin Paladin", "tags": ["sys", "admin", "server", "bash", "deploy", "linux"]},
        {"name": "Web Weaver", "tags": ["web", "html", "css", "react", "node", "frontend"]},
        {"name": "QA Paladin", "tags": ["test", "qa", "bug", "fix"]},
        {"name": "Scholar", "tags": ["study", "read", "learn", "book", "thesis"]},
        {"name": "Bard", "tags": ["write", "blog", "content", "music", "art"]}
    ],
    "xp_goal": 1000,
    "boss_threshold": 120
}

BIG_FONT = {
    '0': [r" ######\  ", r"### __##\ ", r"####\ ## |", r"##\##\## |", r"## \#### |", r"## |\### |", r"\######  /", r" \______/ "],
    '1': [r"   ##\    ", r" #### |   ", r" \_## |   ", r"   ## |   ", r"   ## |   ", r"   ## |   ", r" ######\  ", r" \______| "],
    '2': [r" ######\  ", r"##  __##\ ", r"\__/  ## |", r" ######  |", r"##  ____/ ", r"## |      ", r"########\ ", r"\________|"],
    '3': [r" ######\  ", r"## ___##\ ", r"\__/   ## |", r"  ##### / ", r"  \___##\ ", r"##\   ## |", r"\######  |", r" \______/ "],
    '4': [r"##\   ##\ ", r"## |  ## |", r"## |  ## |", r"######## |", r"\_____## |", r"      ## |", r"      ## |", r"      \__|"],
    '5': [r"#######\  ", r"##  ____| ", r"## |      ", r"#######\  ", r"\_____##\ ", r"##\   ## |", r"\######  |", r" \______/ "],
    '6': [r" ######\  ", r"##  __##\ ", r"## /  \__|", r"#######\  ", r"##  __##\ ", r"## /  ## |", r" ######  |", r" \______/ "],
    '7': [r"########\ ", r"\____##  |", r"    ##  / ", r"   ##  /  ", r"  ##  /   ", r" ##  /    ", r"##  /     ", r"\__/      "],
    '8': [r" ######\  ", r"##  __##\ ", r"## /  ## |", r" ######  |", r"##  __##< ", r"## /  ## |", r"\######  |", r" \______/ "],
    '9': [r" ######\  ", r"##  __##\ ", r"## /  ## |", r"\####### |", r" \____## |", r"##\   ## |", r"\######  |", r" \______/ "],
    ':': [r"        ", r"        ", r"  ##\   ", r"  \__|  ", r"        ", r"  ##\   ", r"  \__|  ", r"        "]
}

PROJECT_COLORS_NAMES = ["Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White", "Crimson", "Lime", "Violet"]

PRIORITY_LABELS = {
    5: "Must be done now",
    4: "Time-sensitive",
    3: "Time-flexible",
    2: "Can be delayed",
    1: "No deadline relevance"
}

XP_MULTIPLIERS = {
    5: 2.0,
    4: 1.5,
    3: 1.2,
    2: 1.0,
    1: 0.8
}
