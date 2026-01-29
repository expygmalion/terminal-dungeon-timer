#!/usr/bin/env python3
import curses
import sys
# Ensure the local directory is in path so we can import the package
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from terminal_dungeon.ui import views, renderer
from terminal_dungeon import state, controller

def main(stdscr):
    renderer.setup_colors()
    controller.init_system()
    curses.curs_set(0)
    
    view = 'HISTORY'
    
    while True:
        if view == 'HISTORY': view = views.show_history(stdscr)
        elif view == 'TIMER': view = views.show_timer_view(stdscr)
        elif view == 'HEATMAP': view = views.show_yearly_heatmap(stdscr)
        elif view == 'WEEKLY': view = views.show_weekly_dungeon(stdscr)
        elif view == 'RAID': view = views.show_daily_raid(stdscr)
        elif view == 'INFO': view = views.show_info_screen(stdscr)
        elif view == 'SETTINGS': view = views.show_settings(stdscr)
        elif view == 'TODO': view = views.show_todo_list(stdscr)
        elif view == 'NEW': view = views.show_quick_start_dialog(stdscr)
        elif view == 'QUIT':
            if state.SESSION['active']: controller.terminate_session()
            break

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass