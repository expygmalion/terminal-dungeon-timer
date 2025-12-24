# Terminal Dungeon Timer

A gamified terminal-based productivity timer that turns your work week into an RPG dungeon crawl. Track your time, build streaks, and visualize your progress with high-fidelity CLI graphics.

## Features

- **Gamified Productivity**: 
  - **Weekly Dungeon**: View your week as a 7-day battleground.
  - **Daily Raid**: Chronological timeline of your day's sessions.
  - **Classes & XP**: Automatically assigned classes (e.g., Code Wizard) based on your project names.
- **Visual Analytics**:
  - **Yearly Heatmap**: GitHub-style contribution graph.
  - **Project Breakdown**: Inventory system showing your "weapons" (projects).
- **Modern CLI UX**:
  - **PiP Timer**: Persistent mini-timer while browsing stats.
  - **Fuzzy Search**: Quickly select projects and tasks.
  - **Nerd Fonts**: Optional high-quality icons.

## Installation

Requires Python 3.

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/terminal-dungeon-timer.git
cd terminal-dungeon-timer

# Run the timer
python3 timer.py
```

### Optional Icons
For the best experience, use a Nerd Font (like 3270 Nerd Font) in your terminal and run:

```bash
python3 timer.py --nerd-fonts
```

## Screens

### 1. The Dashboard (Weekly Dungeon)
Press 'W' to view.

```text
┌─ PLAYER HUD ──────────────────────────────────────┐
│ CLASS: Code Wizard                                │
│ LVL 5 [██████████░░░░░░░░░░] 500/1000 XP          │
└───────────────────────────────────────────────────┘

┌─ THE 7-DAY DUNGEON ───────────────────────────────┐
│ MON   TUE   WED   THU   FRI   SAT   SUN           │
│                                                   │
│ █     █                                           │
│ █     █     █           █                         │
│ ▓     █     █           █                         │
│ ▓     ▒     ▒     ░     ▓                         │
│ ♛     ▒     ░     ░     ▒                         │
└───────────────────────────────────────────────────┘

┌─ LOOT & STATS ────────────────────────────────────┐
│ x4 COMBO!                                         │
│ WEAPONS: Python (60%)  Docs (40%)                 │
└───────────────────────────────────────────────────┘
```

### 2. Daily Raid
Press 'R' to view.

```text
WEEKLY RAID: DAY 3/7

CHRONO-LOG                    BATTLE STATS
────────────────────────────────────────────────────
│ ├─[●] 09:30: Email          QUEST: Project-A
│ ├─[●] 10:15: Daily Standup  OBJ:   Fix Bugs
│ ╞═[★] 11:00: Deep Work
│ └─[○] 14:00: Planning       DURATION: 120 min
                              
                              LOOT DROPS:
                              ████████████
                              
                              ACTIVE BUFFS:
                              * BOSS SLAYER
```

### 3. Yearly Heatmap
Press 'H' to view.

```text
YEARLY ACTIVITY STREAK
1250 contributions in the last year

    Jan  Feb  Mar  Apr  May  Jun  Jul  Aug ...
Mon      ■    ■         ■    ■    ■
Wed ■    ■    ■    ■    ■    ■    ■    ■
Fri ■         ■    ■         ■

                                Less ■ ■ ■ ■ ■ More
```

## Controls

| Key | Action |
| --- | --- |
| **N** | New Session |
| **T** | Go to Timer |
| **H** | Yearly Heatmap |
| **W** | Weekly Dungeon |
| **R** | Daily Raid |
| **I** | Info & Rules |
| **D** | Delete Session |
| **Q** | Quit |
| **Arrows** | Navigation |

## License

MIT
