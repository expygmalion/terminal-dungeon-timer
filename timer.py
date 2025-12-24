#!/usr/bin/env python3
import curses
import time
import json
import os
import sys
import curses.ascii
from datetime import datetime, timedelta

# --- Configuration & Constants ---
DATA_FILE = "timer_history.json"
PRESETS = [5, 10, 15, 20, 25, 30, 45, 60, 90, 120]

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

# --- Global State ---
SESSION = {
    'active': False,
    'state': 'stopped', # running, paused, finished
    'project': "",
    'task': "",
    'duration_secs': 0,
    'start_time': 0,
    'elapsed_before_pause': 0,
    'last_blink': 0,
    'show_colon': True
}

# --- Data Management ---
def load_history():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def get_unique_projects():
    history = load_history()
    return sorted(list(set(i['project'] for i in history if i.get('project'))))

def get_unique_tasks(project_name):
    history = load_history()
    return sorted(list(set(i['task'] for i in history if i.get('project') == project_name and i.get('task'))))

def save_session(session):
    history = load_history()
    history.insert(0, session)
    history = history[:1000]
    with open(DATA_FILE, 'w') as f: json.dump(history, f, indent=2)

def delete_session(index):
    history = load_history()
    if 0 <= index < len(history):
        del history[index]
        with open(DATA_FILE, 'w') as f: json.dump(history, f, indent=2)
        return True
    return False

def format_duration(seconds):
    m = int(seconds // 60); s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def parse_time_str(s):
    try:
        parts = s.split(':')
        if len(parts) == 3: # H:M:S
            return int(parts[0])*60 + int(parts[1]) + int(parts[2])/60
        if len(parts) == 2: # M:S
            return int(parts[0]) + int(parts[1])/60
        if len(parts) == 1: # MIN
            return float(parts[0])
    except: pass
    return None

# --- Timer Logic ---
def tick_timer():
    if not SESSION['active'] or SESSION['state'] != 'running': return
    now = time.time()
    elapsed = SESSION['elapsed_before_pause'] + (now - SESSION['start_time'])
    remaining = SESSION['duration_secs'] - elapsed
    
    if now - SESSION['last_blink'] > 0.5:
        SESSION['show_colon'] = not SESSION['show_colon']
        SESSION['last_blink'] = now
        
    if remaining <= 0:
        SESSION['state'] = 'finished'
        SESSION['show_colon'] = True
        save_session({
            "project": SESSION['project'], "task": SESSION['task'],
            "duration_minutes": SESSION['duration_secs'] // 60,
            "timestamp": datetime.now().isoformat(), "status": "completed"
        })

def start_new_session(project, task, duration_mins):
    SESSION['active'] = True; SESSION['state'] = 'running'
    SESSION['project'] = project; SESSION['task'] = task
    SESSION['duration_secs'] = duration_mins * 60
    SESSION['start_time'] = time.time(); SESSION['elapsed_before_pause'] = 0
    SESSION['show_colon'] = True

def abort_session():
    if not SESSION['active']: return
    elapsed = SESSION['elapsed_before_pause']
    if SESSION['state'] == 'running': elapsed += (time.time() - SESSION['start_time'])
    if SESSION['state'] != 'finished':
        save_session({
            "project": SESSION['project'], "task": SESSION['task'],
            "duration_minutes": SESSION['duration_secs'] // 60,
            "timestamp": datetime.now().isoformat(), "status": "aborted",
            "actual_duration_seconds": int(elapsed)
        })
    SESSION['active'] = False; SESSION['state'] = 'stopped'

# --- TUI Helpers ---
def draw_box(stdscr, y, x, height, width, title=""):
    try:
        h, w = stdscr.getmaxyx()
        if y + height > h or x + width > w: return
        stdscr.attron(curses.color_pair(3))
        stdscr.addch(y, x, curses.ACS_ULCORNER); stdscr.addch(y, x + width - 1, curses.ACS_URCORNER)
        stdscr.addch(y + height - 1, x, curses.ACS_LLCORNER); stdscr.addch(y + height - 1, x + width - 1, curses.ACS_LRCORNER)
        for i in range(1, width - 1): stdscr.addch(y, x + i, curses.ACS_HLINE); stdscr.addch(y + height - 1, x + i, curses.ACS_HLINE)
        for i in range(1, height - 1): stdscr.addch(y + i, x, curses.ACS_VLINE); stdscr.addch(y + i, x + width - 1, curses.ACS_VLINE)
        if title: stdscr.addstr(y, x + 2, f" {title} ")
        stdscr.attroff(curses.color_pair(3))
    except: pass

def draw_big_text(stdscr, y, x, text, color_pair):
    stdscr.attron(color_pair)
    for char_idx, char in enumerate(text):
        if char in BIG_FONT:
            lines = BIG_FONT[char]
            for line_idx, line in enumerate(lines):
                try: stdscr.addstr(y + line_idx, x + (char_idx * 11), line)
                except: pass
    stdscr.attroff(color_pair)

def safe_addstr(stdscr, y, x, text, attr=0):
    try: stdscr.addstr(y, x, text[:stdscr.getmaxyx()[1]-x-1], attr)
    except: pass

def draw_pip_timer(stdscr):
    if not SESSION['active']: return
    h, w = stdscr.getmaxyx()
    pip_w = 24; pip_h = 3; start_x = w - pip_w - 1; start_y = 0
    if SESSION['state'] == 'running': elapsed = SESSION['elapsed_before_pause'] + (time.time() - SESSION['start_time'])
    else: elapsed = SESSION['elapsed_before_pause']
    rem = max(0, SESSION['duration_secs'] - elapsed); t_str = format_duration(rem)
    color = curses.color_pair(4)
    if SESSION['state'] == 'paused': color = curses.color_pair(6)
    elif SESSION['state'] == 'finished': color = curses.color_pair(2)
    try:
        stdscr.attron(color)
        stdscr.addstr(start_y, start_x, "╭" + "─"*(pip_w-2) + "╮")
        stdscr.addstr(start_y+1, start_x, "│" + " "*(pip_w-2) + "│")
        stdscr.addstr(start_y+2, start_x, "╰" + "─"*(pip_w-2) + "╯")
        icon = "▶" if SESSION['state']=='running' else ("⏸" if SESSION['state']=='paused' else "✔")
        txt = f"{icon} {t_str} [T]"
        stdscr.addstr(start_y+1, start_x + (pip_w-len(txt))//2, txt)
        stdscr.attroff(color)
    except: pass

def check_nav_keys(key):
    if key in [ord('h'), ord('H')]: return 'HEATMAP'
    if key in [ord('w'), ord('W')]: return 'WEEKLY'
    if key in [ord('r'), ord('R')]: return 'RAID'
    if key in [ord('i'), ord('I')]: return 'INFO'
    if key in [ord('t'), ord('T')] and SESSION['active']: return 'TIMER'
    return None

def is_subsequence(q, t):
    it = iter(t.lower()); q = q.lower().replace(" ", "")
    return all(c in it for c in q)

def fuzzy_select(stdscr, y, x, prompt, options):
    curses.curs_set(1); inp = ""; sel = 0
    while True:
        tick_timer(); stdscr.erase(); draw_pip_timer(stdscr)
        filt = [o for o in options if is_subsequence(inp, o)] if inp else options[:]
        sel = max(0, min(sel, len(filt)-1)) if filt else -1
        draw_box(stdscr, y, x, 3, 34, prompt); stdscr.addstr(y+1, x+2, inp)
        start = max(0, sel - 7)
        for i in range(8):
            if start+i >= len(filt): break
            attr = curses.A_REVERSE if start+i==sel else 0
            safe_addstr(stdscr, y+3+i, x, f"{ ' > ' if start+i==sel else '   '}{filt[start+i]}", attr)
        stdscr.refresh(); stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k == -1: time.sleep(0.05); continue
        if k in [10, 13]:
            if sel >= 0 and filt:
                if inp == filt[sel]: curses.curs_set(0); return filt[sel]
                inp = filt[sel]
            elif inp: curses.curs_set(0); return inp
        elif k == 27: curses.curs_set(0); return None
        elif k == curses.KEY_UP: sel -= 1
        elif k == curses.KEY_DOWN: sel += 1
        elif k in [curses.KEY_BACKSPACE, 127, 8]: inp = inp[:-1]; sel = 0
        elif 32 <= k <= 126 and len(inp) < 30: inp += chr(k); sel = 0

def select_duration(stdscr):

    h, w = stdscr.getmaxyx(); opts = PRESETS + ["Custom"]; sel = 0

    custom_inp = ""; mode = "MENU"

    while True:

        tick_timer(); stdscr.erase(); draw_pip_timer(stdscr)

        

        top_h = 5; btm_h = len(opts) + 4; total_h = top_h + btm_h

        sy = max(0, (h - total_h) // 2)

        

        draw_box(stdscr, sy, w//2 - 20, top_h, 40, "QUICK ENTRY")

        safe_addstr(stdscr, sy + 1, w//2 - 18, "H:M:S or MIN:", curses.color_pair(2))

        dsp = custom_inp if custom_inp else "00:00:00"

        safe_addstr(stdscr, sy + 2, w//2 - 18, f" {dsp:<15} ", curses.A_REVERSE if mode=="TYPE" else curses.A_DIM)

        

        by = sy + top_h

        if by + btm_h < h:

            draw_box(stdscr, by, w//2 - 20, btm_h, 40, "PRESETS")

            for i, item in enumerate(opts):

                lbl = "Manual Input" if item=="Custom" else f"{item} Minutes"

                attr = curses.A_REVERSE if (i==sel and mode=="MENU") else 0

                safe_addstr(stdscr, by + 2 + i, w//2 - 15, f"{' > ' if (i==sel and mode=='MENU') else '   '}{lbl:<20}", attr)

        else:

            # Fallback if screen too small: just draw list

            safe_addstr(stdscr, by, w//2 - 20, "Screen too small for presets", curses.color_pair(9))

            

        stdscr.addstr(h - 2, 2, "[Arrows/Digits] Nav/Type  [Enter] Start", curses.color_pair(4)); stdscr.refresh()

        stdscr.timeout(50); k = stdscr.getch()

        

        if k == -1: continue

        if mode == "MENU":

            if k == curses.KEY_UP:

                if sel == 0: mode = "TYPE"

                else: sel -= 1

            elif k == curses.KEY_DOWN: sel = min(len(opts)-1, sel + 1)

            elif k in [10, 13]:

                if opts[sel] == "Custom": mode = "TYPE"

                else: return opts[sel]

            elif 48 <= k <= 57: mode = "TYPE"; custom_inp = chr(k)

            elif k == 27: return None

        else:

            if k in [10, 13]:

                val = parse_time_str(custom_inp)

                if val: return val

            elif k == 27: mode = "MENU"; custom_inp = ""

            elif k in [127, 8, curses.KEY_BACKSPACE]:

                custom_inp = custom_inp[:-1]

                if not custom_inp: mode = "MENU"

            elif (48 <= k <= 57 or k == ord(':')) and len(custom_inp) < 10: custom_inp += chr(k)

            elif k == curses.KEY_DOWN: mode = "MENU"; sel = 0

# --- Main Views ---

def show_history(stdscr):
    idx = 0; scroll = 0; use_nerd = "--nerd-fonts" in sys.argv
    history = load_history(); last_load = time.time(); stdscr.timeout(50)
    while True:
        tick_timer()
        if time.time() - last_load > 1.0: history = load_history(); last_load = time.time()
        stdscr.erase(); h, w = stdscr.getmaxyx()
        tt, ty, ratio = calculate_stats()
        r_str = f"{ratio:.2f}x" if ratio != float('inf') else "INF"
        safe_addstr(stdscr, 0, 2, f"TODAY: {tt:.1f}m | YEST: {ty:.1f}m | RATIO: {r_str}", curses.color_pair(2)|curses.A_BOLD)
        if use_nerd:
            header = f"{' DATE':<19} | {' PROJ':<12} | {' TASK':<20} | {' DUR':<5} | {' STATUS':<12} | {' MULT'}"
        else:
            header = f"{'DATE':<19} | {'PROJECT':<12} | {'TASK':<20} | {'DUR':<5} | {'STATUS':<12} | {'MULT'}"
        safe_addstr(stdscr, 2, 2, header, curses.color_pair(3)); safe_addstr(stdscr, 3, 2, "-"*min(len(header), w-2), curses.color_pair(3))
        list_h = max(1, h - 6)
        if history: idx = max(0, min(idx, len(history)-1))
        if idx < scroll: scroll = idx
        elif idx >= scroll + list_h: scroll = idx - list_h + 1
        for i in range(list_h):
            ii = scroll + i
            if ii >= len(history): break
            it = history[ii]; dt = it.get('timestamp','')[:19]; st = "SUCCESS" if it.get('status')=='completed' else "TERM"
            dm = f"{it.get('duration_minutes',0)}m" if st=="SUCCESS" else f"{int(it.get('actual_duration_seconds',0)//60)}m"
            if use_nerd: st = " SUCCESS" if st=="SUCCESS" else " TERM"
            attr = curses.color_pair(1)|curses.A_REVERSE if ii==idx else 0
            safe_addstr(stdscr, 4+i, 2, f"{dt:<19} | {it.get('project','-')[:12]:<12} | {it.get('task','-')[:20]:<20} | {dm:<5} | {st:<12} | {'1.0x' if st.endswith('SUCCESS') else '-'}", attr)
        safe_addstr(stdscr, h-1, 2, "[N] New  [D] Del  [H] Heat  [W] Week  [R] Raid  [I] Info  [Q] Quit", curses.color_pair(4))
        draw_pip_timer(stdscr); stdscr.refresh(); k = stdscr.getch()
        if k == -1: continue
        nav = check_nav_keys(k); 
        if nav: return nav
        if k in [ord('n'), ord('N')]: return 'NEW'
        elif k in [ord('d'), ord('D')] and history: 
            # Confirmation prompt
            msg = " DELETE SESSION? (y/n) "
            safe_addstr(stdscr, h-1, 2, " " * (w-3))
            safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
            stdscr.refresh()
            stdscr.timeout(-1)
            conf_k = stdscr.getch()
            stdscr.timeout(50)
            if conf_k in [ord('y'), ord('Y')]:
                delete_session(idx); history = load_history()
        elif k in [ord('q'), ord('Q')]: return 'QUIT'
        elif k == curses.KEY_UP: idx -= 1
        elif k == curses.KEY_DOWN: idx += 1

def show_timer_view(stdscr):
    btn = 0
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx()
        if not SESSION['active']: return 'HISTORY'
        draw_box(stdscr, 1, 2, 6, max(40, w - 35), "DETAILS")
        safe_addstr(stdscr, 2, 4, f"PROJECT: {SESSION['project']}"); safe_addstr(stdscr, 3, 4, f"TASK:    {SESSION['task']}")
        draw_box(stdscr, 1, max(40, w - 35) + 3, 6, 30, "SYSTEM"); safe_addstr(stdscr, 3, max(40, w - 35) + 5, f"{datetime.now().strftime('%H:%M:%S')}")
        elapsed = SESSION['elapsed_before_pause'] + (time.time()-SESSION['start_time'] if SESSION['state']=='running' else 0)
        rem = max(0, SESSION['duration_secs'] - elapsed); t_str = format_duration(rem)
        color = curses.color_pair(4) if SESSION['state']=='running' else curses.color_pair(6)
        if SESSION['state']=='finished': color = curses.color_pair(2)
        draw_big_text(stdscr, h//2 - 2, w//2 - 28, t_str if SESSION['show_colon'] else t_str.replace(":"," "), color)
        bar_y = h//2 + 7; bar_w = min(60, w - 10)
        if bar_w > 0:
            draw_box(stdscr, bar_y - 1, w//2 - bar_w//2 - 2, 3, bar_w + 4)
            pct = 1.0 - (rem / SESSION['duration_secs']) if SESSION['duration_secs'] > 0 else 1.0
            if SESSION['state'] == 'finished': pct = 1.0
            fld = int(bar_w * pct)
            safe_addstr(stdscr, bar_y, w//2 - bar_w//2, "█"*fld + "░"*(bar_w-fld), curses.color_pair(3))
        safe_addstr(stdscr, bar_y+3, w//2 - 10, f"STATUS: {SESSION['state'].upper()}", color|curses.A_BOLD)
        btns = ["MENU", "RESTART", "QUIT"] if SESSION['state']=='finished' else ["PAUSE" if SESSION['state']=='running' else "START", "RESTART", "BACK", "QUIT"]
        t_w = sum(len(b)+4 for b in btns) + (len(btns)-1)*2; x = w//2 - t_w//2
        for i, lbl in enumerate(btns):
            safe_addstr(stdscr, h-4, x, f"[ {lbl} ]", curses.color_pair(1)|(curses.A_REVERSE if i==btn else 0)); x += len(lbl)+6
        stdscr.refresh(); stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k == -1: time.sleep(0.05); continue
        nav = check_nav_keys(k); 
        if nav and nav != 'TIMER': return nav
        if k == curses.KEY_LEFT: btn = max(0, btn - 1)
        elif k == curses.KEY_RIGHT: btn = min(len(btns)-1, btn + 1)
        elif k in [10, 13]:
            sel = btns[btn]
            if sel in ["BACK", "MENU"]: return 'HISTORY'
            elif sel == "QUIT": abort_session(); return 'QUIT'
            elif sel == "RESTART": abort_session(); start_new_session(SESSION['project'], SESSION['task'], SESSION['duration_secs']//60); return 'TIMER'
            elif sel == "START": SESSION['state']='running'; SESSION['start_time']=time.time()
            elif sel == "PAUSE": SESSION['state']='paused'; SESSION['elapsed_before_pause']+= (time.time()-SESSION['start_time'])
        elif k == 27: return 'HISTORY'

def show_yearly_heatmap(stdscr):
    if curses.can_change_color():
        curses.init_color(20, 86, 105, 133); curses.init_color(21, 54, 266, 160); curses.init_color(22, 0, 427, 196)
        curses.init_color(23, 149, 651, 255); curses.init_color(24, 223, 827, 325)
        for i in range(20, 25): curses.init_pair(i, i, -1)
    history = load_history(); yd = {}; sy = datetime.now().date() - timedelta(weeks=52); sy -= timedelta(days=sy.weekday())
    total_c = 0
    for i in history:
        try:
            d = datetime.fromisoformat(i['timestamp']).date(); dur = i['duration_minutes'] if i.get('status')=='completed' else (i.get('actual_duration_seconds',0)/60)
            if 0 <= (d - sy).days < 371: yd[((d-sy).days//7, d.weekday())] = yd.get(((d-sy).days//7, d.weekday()),0) + dur; total_c += 1
        except: pass
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        safe_addstr(stdscr, 1, 4, f"{total_c} contributions in the last year", curses.color_pair(1)|curses.A_BOLD)
        m_str = "    "; curr_m = -1
        for wk in range(53):
             d = sy + timedelta(weeks=wk)
             if d.month != curr_m:
                 nm = d.strftime("%b"); tgt = 4 + (wk * 2)
                 if tgt > len(m_str): m_str += " " * (tgt - len(m_str))
                 m_str += nm; curr_m = d.month
        safe_addstr(stdscr, 2, 0, m_str[:w])
        for dy in range(7):
            lbl = ""; 
            if dy == 1: lbl = "Mon" 
            elif dy == 3: lbl = "Wed" 
            elif dy == 5: lbl = "Fri"
            safe_addstr(stdscr, dy+3, 0, f"{lbl:<3}")
            for wk in range(53):
                if 4+(wk*2) >= w: break
                val = yd.get((wk, dy), 0)
                if curses.can_change_color(): attr = curses.color_pair(20) if val==0 else (curses.color_pair(21) if val<=15 else (curses.color_pair(22) if val<=30 else (curses.color_pair(23) if val<=60 else curses.color_pair(24))))
                else: attr = (curses.color_pair(1)|curses.A_DIM) if val==0 else ((curses.color_pair(21)|curses.A_DIM) if val<=15 else (curses.color_pair(22) if val<=30 else ((curses.color_pair(23)|curses.A_BOLD) if val<=60 else (curses.color_pair(24)|curses.A_BOLD))))
                safe_addstr(stdscr, dy+3, 4+(wk*2), "■ ", attr)
        safe_addstr(stdscr, h-1, 2, "PRESS [ESC] BACK", curses.color_pair(1))
        stdscr.refresh(); stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k in [27, ord('q'), ord('Q')]: return 'HISTORY'
        nav = check_nav_keys(k); 
        if nav: return nav
        time.sleep(0.05)

def show_weekly_dungeon(stdscr):
    curses.init_pair(7, curses.COLOR_MAGENTA, -1); curses.init_pair(8, curses.COLOR_CYAN, -1); curses.init_pair(9, curses.COLOR_RED, -1)
    history = load_history(); now = datetime.now(); today = now.date(); curr_wk = today - timedelta(days=today.weekday())
    daily_xp = [0]*7; proj_xp = {}; wk_total = 0
    for i in history:
        try:
            ts = datetime.fromisoformat(i['timestamp']); dt = ts.date()
            dur = i['duration_minutes'] if i.get('status')=='completed' else (i.get('actual_duration_seconds',0)/60)
            if curr_wk <= dt < curr_wk + timedelta(days=7):
                daily_xp[dt.weekday()] += dur; wk_total += dur
                p = i.get('project', 'Unknown'); proj_xp[p] = proj_xp.get(p, 0) + dur
        except: pass
    streak = 0; check = today
    while True:
        f = False
        for i in history:
            try:
                if datetime.fromisoformat(i['timestamp']).date() == check: f = True; break
            except: pass
        if f: streak += 1; check -= timedelta(days=1)
        else: break
    max_v = max(daily_xp) if max(daily_xp + [0]) > 0 else 1
    frame = 0
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        draw_box(stdscr, 1, 0, 5, w, "PLAYER HUD")
        top_p = max(proj_xp, key=proj_xp.get) if proj_xp else "Novice"
        if "code" in top_p.lower() or "py" in top_p.lower(): p_class = "Code Wizard"
        elif "data" in top_p.lower(): p_class = "Data Ronin"
        elif "sys" in top_p.lower(): p_class = "SysAdmin Paladin"
        elif "web" in top_p.lower(): p_class = "Web Weaver"
        else: p_class = f"{top_p} Mancer"
        safe_addstr(stdscr, 2, 2, f"CLASS: {p_class}", curses.color_pair(8)|curses.A_BOLD)
        xp_p = min(1.0, wk_total/1000); b_l = max(10, w - 40); fld = int(b_l * xp_p)
        safe_addstr(stdscr, 3, 2, f"LVL {int(wk_total/60)} ([{'█'*fld + '░'*(b_l-fld)}]) {int(wk_total)}/1000 XP")
        safe_addstr(stdscr, 2, w - 26, "STREAK ACTIVE" if streak > 0 else "OFFLINE", curses.color_pair(4) if streak>0 else curses.color_pair(9))
        bg_h = max(10, h - 15); draw_box(stdscr, 6, 0, bg_h, w, "THE 7-DAY DUNGEON")
        b_w = max(2, (w-14)//7); spc = b_w + 1; days = ["MON","TUE","WED","THU","FRI","SAT","SUN"]
        graph_h = bg_h - 4
        for i in range(7):
            f_h = int((daily_xp[i]/max_v)*graph_h); c_h = min(f_h, frame); x = 4+(i*spc); b_y = 6 + bg_h - 2
            safe_addstr(stdscr, b_y+1, x, days[i][:b_w], curses.A_BOLD)
            val = daily_xp[i]; is_crit = val > 120
            for bh in range(c_h):
                yy = b_y-bh; rel = bh / (graph_h if graph_h else 1); char = "░"
                if rel > 0.7: char = "█"
                elif rel > 0.4: char = "▓"
                elif rel > 0.1: char = "▒"
                safe_addstr(stdscr, yy, x, char*b_w, curses.color_pair(7)|curses.A_BOLD if is_crit else curses.color_pair(8))
            if is_crit and c_h == f_h: safe_addstr(stdscr, b_y - c_h - 1, x + b_w//2, "♛", curses.color_pair(6)|curses.A_BOLD)
        ft_y = 6 + bg_h; draw_box(stdscr, ft_y, 0, h - ft_y, w, "LOOT & STATS")
        safe_addstr(stdscr, ft_y+1, 2, f"x{streak} COMBO!", curses.color_pair(6)|curses.A_BOLD)
        inv = "WEAPONS: "; sp = sorted(proj_xp.items(), key=lambda x: x[1], reverse=True)[:2]
        for p, d in sp: inv += f"{p} ({int(d/wk_total*100)}%) "
        safe_addstr(stdscr, ft_y+3, 2, inv, curses.color_pair(8))
        safe_addstr(stdscr, ft_y+1, w//2, "QUEST LOG:", curses.A_UNDERLINE)
        for idx, q in enumerate(history[:3]):
            if ft_y + 2 + idx < h - 1: safe_addstr(stdscr, ft_y+2+idx, w//2, f"[✔] {q.get('task','-')[:20]} (+{q.get('duration_minutes',0)} XP)")
        safe_addstr(stdscr, h-1, 2, "[ESC] Return", curses.color_pair(9))
        stdscr.refresh(); stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k == -1:
            if frame < graph_h: frame += 1; time.sleep(0.02)
            else: time.sleep(0.05)
            continue
        if k in [27, ord('q'), ord('Q')]: return 'HISTORY'
        nav = check_nav_keys(k); 
        if nav: return nav

def show_daily_raid(stdscr):
    curses.init_pair(10, curses.COLOR_MAGENTA, -1); curses.init_pair(11, curses.COLOR_YELLOW, -1); curses.init_pair(12, curses.COLOR_CYAN, -1)
    history = load_history(); now = datetime.now(); today = now.date()
    todays = [i for i in history if datetime.fromisoformat(i['timestamp']).date()==today]
    todays.sort(key=lambda x: x['timestamp']); sel = len(todays)-1 if todays else 0; scr = 0
    boss_idx = -1; max_d = 0
    if todays:
        for i,s in enumerate(todays):
            d = s.get('duration_minutes',0) if s.get('status')=='completed' else s.get('actual_duration_seconds',0)/60
            if d > max_d: max_d = d; boss_idx = i
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        start_wk = today - timedelta(days=today.weekday())
        for i in range(7):
            d = start_wk + timedelta(days=i); char = "█" if d == today else ("▄" if d < today else "_")
            safe_addstr(stdscr, 1, 2 + (i*4), char, curses.color_pair(12)|curses.A_BOLD if d == today else curses.A_DIM)
        safe_addstr(stdscr, 1, 35, f"WEEKLY RAID: DAY {today.weekday()+1}/7", curses.color_pair(12)|curses.A_BOLD)
        split = int(w*0.6)
        for y in range(3, h): safe_addstr(stdscr, y, split, "║", curses.color_pair(12))
        safe_addstr(stdscr, 3, 2, "CHRONO-LOG", curses.color_pair(12)|curses.A_BOLD); safe_addstr(stdscr, 3, split+2, "BATTLE STATS", curses.color_pair(12)|curses.A_BOLD); safe_addstr(stdscr, 4, 0, "═"*w, curses.color_pair(12))
        list_h = h - 6
        if not todays: safe_addstr(stdscr, 6, 2, "Dungeon Empty...", curses.A_DIM)
        else:
            if sel < scr: scr = sel
            elif sel >= scr + list_h: scr = sel - list_h + 1
            for i in range(list_h):
                idx = scr + i; 
                if idx >= len(todays): break
                s = todays[idx]; ts = datetime.fromisoformat(s['timestamp']); tm = ts.strftime("%H:%M"); tk = s.get('task', 'Unknown')[:25]
                mk = "★" if idx == boss_idx else "●"; col = curses.color_pair(10)|curses.A_BOLD if idx==boss_idx else curses.color_pair(1)
                pre = "├─" if idx < len(todays)-1 else "└─"
                attr = curses.color_pair(12)|curses.A_REVERSE if idx==sel else col
                safe_addstr(stdscr, 5+i, 2, f"│ {pre}[{mk}] {tm}: {tk}", attr)
        if todays and sel < len(todays):
            ss = todays[sel]; sy = 5; x = split+2; safe_addstr(stdscr, sy, x, f"QUEST: {ss.get('project','-')}", curses.color_pair(12)|curses.A_BOLD); safe_addstr(stdscr, sy+1, x, f"OBJ:   {ss.get('task','-')}", curses.color_pair(1))
            du = ss.get('duration_minutes',0) if ss.get('status')=='completed' else ss.get('actual_duration_seconds',0)/60
            safe_addstr(stdscr, sy+3, x, f"DURATION: {int(du)} min", curses.color_pair(11)|curses.A_BOLD); safe_addstr(stdscr, sy+5, x, "LOOT DROPS:", curses.color_pair(12)|curses.A_UNDERLINE)
            loot = "█ " * int(du/5); safe_addstr(stdscr, sy+6, x, loot if loot else "░", curses.color_pair(10)|curses.A_BOLD)
            ts = datetime.fromisoformat(ss['timestamp']); mds = []
            if ts.hour < 9: mds.append("EARLY BIRD")
            if ts.hour >= 23: mds.append("MIDNIGHT OIL")
            if sel == boss_idx: mds.append("BOSS SLAYER")
            if mds:
                safe_addstr(stdscr, sy+8, x, "ACTIVE BUFFS:", curses.color_pair(12)|curses.A_UNDERLINE)
                for mi, m in enumerate(mds): safe_addstr(stdscr, sy+9+mi, x, f"⚡ {m}", curses.color_pair(11)|curses.A_BOLD)
        safe_addstr(stdscr, h-1, 2, "[Arrows] Select  [ESC] Retreat", curses.color_pair(1)|curses.A_BOLD)
        stdscr.refresh(); stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k == -1: time.sleep(0.05); continue
        if k in [27, ord('q'), ord('Q')]: return 'HISTORY'
        nav = check_nav_keys(k); 
        if nav: return nav
        if k == curses.KEY_UP: sel = max(0, sel-1)
        elif k == curses.KEY_DOWN: sel = min(len(todays)-1, sel+1)

def show_info_screen(stdscr):
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        draw_box(stdscr, 1, 2, h-2, w-4, "ADVENTURER'S MANUAL")
        
        y = 3; x = 5
        if y < h-2: safe_addstr(stdscr, y, x, "1. THE GOAL: FILL THE BAR", curses.color_pair(12)|curses.A_BOLD)
        if y+1 < h-2: safe_addstr(stdscr, y+1, x, "   1 Min = 1 XP. Weekly Goal: 1000 XP.", curses.color_pair(1))
        if y+2 < h-2: safe_addstr(stdscr, y+2, x+3, f"LVL 5 [{'█'*10 + '░'*10}]", curses.color_pair(7))
        
        y += 5
        if y < h-2: safe_addstr(stdscr, y, x, "2. COMBAT: BUILD THE PILLARS", curses.color_pair(9)|curses.A_BOLD)
        if y+1 < h-2: safe_addstr(stdscr, y+1, x, "   Taller bars = More work done today.", curses.color_pair(1))
        if y+2 < h-2: safe_addstr(stdscr, y+2, x+3, "█  (Crit!)  ♛ > 2 Hrs", curses.color_pair(7)|curses.A_BOLD)
        if y+3 < h-2: safe_addstr(stdscr, y+3, x+3, "▓  (High)", curses.color_pair(8))
        if y+4 < h-2: safe_addstr(stdscr, y+4, x+3, "▒  (Med)", curses.color_pair(8)|curses.A_DIM)
        
        y += 6
        if y < h-2: safe_addstr(stdscr, y, x, "3. CONTROLS", curses.color_pair(11)|curses.A_BOLD)
        keys = [("[N]","New"), ("[T]","Timer"), ("[H]","Heatmap"), ("[W]","Dungeon"), ("[R]","Raid"), ("[D]","Delete")]
        for i, (k, desc) in enumerate(keys):
            if y+1+(i//2) < h-2: 
                col = 3 if i%2==0 else 25
                row = y+1+(i//2)
                safe_addstr(stdscr, row, x+col, f"{k} {desc}", curses.color_pair(1))

        safe_addstr(stdscr, h-3, w//2 - 10, "Press any key to return", curses.color_pair(9)|curses.A_BOLD)
        stdscr.refresh(); stdscr.timeout(50); k = stdscr.getch()
        if k == -1: continue
        nav = check_nav_keys(k); 
        if nav and nav != 'INFO': return nav
        return 'HISTORY'

def calculate_stats():
    history = load_history(); today = datetime.now().date(); yest = today - timedelta(days=1); tt = 0; ty = 0
    for i in history:
        try:
            d = datetime.fromisoformat(i['timestamp']).date(); dur = i['duration_minutes'] if i.get('status')=='completed' else (i.get('actual_duration_seconds',0)/60)
            if d == today: tt += dur
            elif d == yest: ty += dur
        except: pass
    return tt, ty, (tt/ty if ty else (float('inf') if tt else 0))

def main(stdscr):
    curses.start_color(); curses.use_default_colors()
    for i, c in enumerate([curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_YELLOW], 1): curses.init_pair(i, c, -1)
    curses.curs_set(0); view = 'HISTORY'
    while True:
        if view == 'HISTORY': view = show_history(stdscr)
        elif view == 'TIMER': view = show_timer_view(stdscr)
        elif view == 'HEATMAP': view = show_yearly_heatmap(stdscr)
        elif view == 'WEEKLY': view = show_weekly_dungeon(stdscr)
        elif view == 'RAID': view = show_daily_raid(stdscr)
        elif view == 'INFO': view = show_info_screen(stdscr)
        elif view == 'NEW':
            stdscr.erase(); h, w = stdscr.getmaxyx()
            p = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "PROJECT", get_unique_projects())
            if not p: view = 'HISTORY'; continue
            t = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "TASK", get_unique_tasks(p))
            if not t: view = 'HISTORY'; continue
            d = select_duration(stdscr)
            if not d: view = 'HISTORY'; continue
            start_new_session(p, t, d); view = 'TIMER'
        elif view == 'QUIT':
            if SESSION['active']: abort_session()
            break

if __name__ == "__main__":
    try: curses.wrapper(main)
    except KeyboardInterrupt: print("\nExited.")