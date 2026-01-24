#!/usr/bin/env python3
import curses
import time
import json
import os
import sys
import curses.ascii
from datetime import datetime, timedelta
import uuid

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

# --- Global State ---
SESSION = {
    'active': False,
    'state': 'stopped', 
    'project': "",
    'task': "",
    'duration_secs': 0,
    'start_time': 0,
    'elapsed_before_pause': 0,
    'last_blink': 0,
    'show_colon': True
}

UNDO_STACK = []

# --- Data Management ---
def load_todos():
    if not os.path.exists(TODO_FILE): return []
    try:
        with open(TODO_FILE, 'r') as f: return json.load(f)
    except: return []

def save_todos(todos):
    with open(TODO_FILE, 'w') as f: json.dump(todos, f, indent=2)

def add_todo(content, date_str, project, tags):
    todos = load_todos()
    new_todo = {
        "id": str(uuid.uuid4()),
        "content": content,
        "date": date_str,
        "project": project if project else "General",
        "tags": tags,
        "status": "pending",
        "timestamp": datetime.now().isoformat()
    }
    todos.append(new_todo)
    save_todos(todos)
    
    if project and project != "General" and tags:
        cfg = load_config()
        if project not in cfg['project_tags']:
            cfg['project_tags'][project] = []
        
        changed = False
        for t in tags:
            if t not in cfg['project_tags'][project]:
                cfg['project_tags'][project].append(t)
                changed = True
        
        if changed:
            save_config(cfg)

def complete_matching_todo(project, content):
    todos = load_todos()
    changed = False
    for t in todos:
        if t.get('project') == project and t.get('content') == content and t.get('status') == 'pending':
            t['status'] = 'done'
            changed = True
    if changed: save_todos(todos)

def toggle_todo(todo_id):
    todos = load_todos()
    target = None
    for t in todos:
        if t['id'] == todo_id:
            target = t
            t['status'] = 'done' if t['status'] == 'pending' else 'pending'
            break
    save_todos(todos)
    
    # "Sanction as completed in 30min" logic
    if target and target['status'] == 'done':
        # Create a history entry
        session = {
            "project": target.get('project', 'General'),
            "task": target.get('content', 'Unknown'),
            "duration_minutes": 30,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "manual_log": True
        }
        save_session(session)
        # Update class progression if needed (handled by determining class on load)

def delete_todo(todo_id):
    todos = load_todos()
    item = next((t for t in todos if t['id'] == todo_id), None)
    if item:
        UNDO_STACK.append({'type': 'todo', 'data': item})
        todos = [t for t in todos if t['id'] != todo_id]
        save_todos(todos)

def add_project(name, color_id=None):
    if not name: return
    cfg = load_config()
    if name not in cfg['project_tags']:
        cfg['project_tags'][name] = []
        if color_id:
             if 'project_colors' not in cfg: cfg['project_colors'] = {}
             cfg['project_colors'][name] = color_id
        save_config(cfg)

def delete_project(name):
    cfg = load_config()
    if name in cfg['project_tags']:
        # Also undo color
        col = cfg.get('project_colors', {}).get(name)
        UNDO_STACK.append({'type': 'project', 'data': {'name': name, 'tags': cfg['project_tags'][name], 'color': col}})
        del cfg['project_tags'][name]
        if 'project_colors' in cfg and name in cfg['project_colors']:
            del cfg['project_colors'][name]
        save_config(cfg)

def restore_last_deleted_item():
    if not UNDO_STACK: return False
    item = UNDO_STACK.pop()
    if item['type'] == 'todo':
        todos = load_todos()
        todos.append(item['data'])
        save_todos(todos)
    elif item['type'] == 'project':
        cfg = load_config()
        p_name = item['data']['name']
        p_tags = item['data']['tags']
        cfg['project_tags'][p_name] = p_tags
        if item['data'].get('color'):
             if 'project_colors' not in cfg: cfg['project_colors'] = {}
             cfg['project_colors'][p_name] = item['data']['color']
        save_config(cfg)
    return True

def load_history():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def load_config():
    if not os.path.exists(CONFIG_FILE): return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            # Simple merge to ensure keys exist
            for k, v in DEFAULT_CONFIG.items():
                if k not in data: data[k] = v
            return data
    except: return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f: json.dump(cfg, f, indent=2)

def get_unique_projects():
    history = load_history()
    cfg = load_config()
    hist_projs = set(i['project'] for i in history if i.get('project'))
    cfg_projs = set(cfg.get('project_tags', {}).keys())
    return sorted(list(hist_projs.union(cfg_projs)))

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

def determine_class(project_name):
    cfg = load_config()
    # 1. Check direct project tags
    tags = cfg['project_tags'].get(project_name, [])
    
    # 2. Add words from project name as implicit tags
    if project_name:
        tags.extend(project_name.lower().replace("-", " ").split())
    
    # 3. Match against classes
    best_match = "Novice"
    max_matches = 0
    
    for cls in cfg['classes']:
        matches = sum(1 for t in cls['tags'] if any(pt in t or t in pt for pt in tags))
        if matches > max_matches:
            max_matches = matches
            best_match = cls['name']
            
    if max_matches == 0 and project_name:
        return f"{project_name} Mancer"
    
    return best_match

def format_duration(seconds):
    m = int(seconds // 60); s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def parse_time_str(s):
    try:
        parts = s.split(':')
        if len(parts) == 3: return int(parts[0])*60 + int(parts[1]) + int(parts[2])/60
        if len(parts) == 2: return int(parts[0]) + int(parts[1])/60
        if len(parts) == 1: return float(parts[0])
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
        SESSION['state'] = 'finished'; SESSION['show_colon'] = True
        save_session({"project": SESSION['project'], "task": SESSION['task'], "duration_minutes": SESSION['duration_secs'] // 60, "timestamp": datetime.now().isoformat(), "status": "completed"})
        complete_matching_todo(SESSION['project'], SESSION['task'])

def start_new_session(project, task, duration_mins):
    SESSION['active'] = True; SESSION['state'] = 'running'
    SESSION['project'] = project; SESSION['task'] = task
    SESSION['duration_secs'] = duration_mins * 60
    SESSION['start_time'] = time.time(); SESSION['elapsed_before_pause'] = 0; SESSION['show_colon'] = True

def terminate_session():
    if not SESSION['active']: return
    elapsed = SESSION['elapsed_before_pause']
    if SESSION['state'] == 'running': elapsed += (time.time() - SESSION['start_time'])
    if SESSION['state'] != 'finished':
        save_session({"project": SESSION['project'], "task": SESSION['task'], "duration_minutes": SESSION['duration_secs'] // 60, "timestamp": datetime.now().isoformat(), "status": "terminated", "actual_duration_seconds": int(elapsed)})
    SESSION['active'] = False; SESSION['state'] = 'stopped'

def pause_timer():
    if SESSION['state'] == 'running':
        SESSION['state'] = 'paused'
        SESSION['elapsed_before_pause'] += (time.time() - SESSION['start_time'])

def resume_timer():
    if SESSION['state'] == 'paused':
        SESSION['state'] = 'running'
        SESSION['start_time'] = time.time()

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
    h, w = stdscr.getmaxyx(); pip_w = 24; start_x = w - pip_w - 1
    if SESSION['state'] == 'running': elapsed = SESSION['elapsed_before_pause'] + (time.time() - SESSION['start_time'])
    else: elapsed = SESSION['elapsed_before_pause']
    rem = max(0, SESSION['duration_secs'] - elapsed); t_str = format_duration(rem)
    color = curses.color_pair(4)
    if SESSION['state'] == 'paused': color = curses.color_pair(6)
    elif SESSION['state'] == 'finished': color = curses.color_pair(2)
    try:
        stdscr.attron(color)
        stdscr.addstr(0, start_x, "╭" + "─"*(pip_w-2) + "╮")
        stdscr.addstr(1, start_x, "│" + " "*(pip_w-2) + "│")
        stdscr.addstr(2, start_x, "╰" + "─"*(pip_w-2) + "╯")
        icon = "▶" if SESSION['state']=='running' else ("⏸" if SESSION['state']=='paused' else "✔")
        txt = f"{icon} {t_str} [T]"
        stdscr.addstr(1, start_x + (pip_w-len(txt))//2, txt)
        stdscr.attroff(color)
    except: pass

def check_nav_keys(key):
    if key in [ord('h'), ord('H')]: return 'HEATMAP'
    if key in [ord('w'), ord('W')]: return 'WEEKLY'
    if key in [ord('r'), ord('R')]: return 'RAID'
    if key in [ord('i'), ord('I')]: return 'INFO'
    if key in [ord('s'), ord('S')]: return 'SETTINGS'
    if key in [ord('t'), ord('T')] and SESSION['active']: return 'TIMER'
    if key in [ord('l'), ord('L')]: return 'TODO'
    return None

def is_subsequence(q, t):
    it = iter(t.lower()); q = q.lower().replace(" ", "")
    return all(c in it for c in q)

def text_input(stdscr, y, x, prompt, default=""):
    curses.curs_set(1); inp = default
    while True:
        tick_timer(); stdscr.erase(); draw_pip_timer(stdscr)
        draw_box(stdscr, y, x, 3, 40, prompt)
        safe_addstr(stdscr, y+1, x+2, inp)
        stdscr.refresh()
        stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k == -1: time.sleep(0.05); continue
        if k in [10, 13]: curses.curs_set(0); return inp
        elif k == 27: curses.curs_set(0); return None
        elif k in [curses.KEY_BACKSPACE, 127, 8]: inp = inp[:-1]
        elif 32 <= k <= 126 and len(inp) < 36: inp += chr(k)

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
                safe_addstr(stdscr, by + 2 + i, w//2 - 15, f"{ ' > ' if (i==sel and mode=='MENU') else '   '}{lbl:<20}", attr)
        else: safe_addstr(stdscr, by, w//2 - 20, "Screen too small for presets", curses.color_pair(9))
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
                val = parse_time_str(custom_inp); 
                if val: return val
            elif k == 27: mode = "MENU"; custom_inp = ""
            elif k in [127, 8, curses.KEY_BACKSPACE]:
                custom_inp = custom_inp[:-1]
                if not custom_inp: mode = "MENU"
            elif (48 <= k <= 57 or k == ord(':')) and len(custom_inp) < 10: custom_inp += chr(k)
            elif k == curses.KEY_DOWN: mode = "MENU"; sel = 0

# --- Screens ---

def show_settings(stdscr):
    cfg = load_config(); opts = ["Manage Projects", "Manage Classes", "Save & Return"]
    sel = 0
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        draw_box(stdscr, h//2 - 6, w//2 - 20, 12, 40, "SETTINGS")
        for i, opt in enumerate(opts):
            attr = curses.A_REVERSE if i == sel else 0
            safe_addstr(stdscr, h//2 - 4 + (i*2), w//2 - 15, f"{opt:<30}", attr)
        stdscr.refresh(); stdscr.timeout(50); k = stdscr.getch()
        if k == -1: continue
        if k == curses.KEY_UP: sel = max(0, sel-1)
        elif k == curses.KEY_DOWN: sel = min(len(opts)-1, sel+1)
        elif k in [10, 13]:
            if sel == 0: # Manage Projects
                projs = get_unique_projects() + ["+ ADD NEW PROJECT"]
                p = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "SELECT PROJECT", projs)
                if p == "+ ADD NEW PROJECT":
                    new_p = text_input(stdscr, h//2, w//2 - 20, "PROJECT NAME:")
                    if new_p: add_project(new_p); cfg = load_config()
                elif p:
                    act = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, f"MANAGE {p}", ["Edit Tags", "Delete Project", "Cancel"])
                    if act == "Edit Tags":
                        curr_tags = cfg['project_tags'].get(p, [])
                        val = text_input(stdscr, h//2, w//2 - 20, f"TAGS FOR '{p}' (comma sep):", ",".join(curr_tags))
                        if val is not None:
                            cfg['project_tags'][p] = [t.strip() for t in val.split(',') if t.strip()]
                    elif act == "Delete Project":
                        msg = f" DELETE PROJECT '{p}'? (y/n) "
                        safe_addstr(stdscr, h-1, 2, " " * (w-3))
                        safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
                        stdscr.refresh()
                        stdscr.timeout(-1)
                        if stdscr.getch() in [ord('y'), ord('Y')]:
                            delete_project(p); cfg = load_config()
                        stdscr.timeout(50)
            elif sel == 1: # Manage Classes
                cls_names = [c['name'] for c in cfg['classes']] + ["+ ADD NEW CLASS"]
                c = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "SELECT CLASS", cls_names)
                if c == "+ ADD NEW CLASS":
                    name = text_input(stdscr, h//2, w//2 - 20, "NEW CLASS NAME:")
                    if name:
                        tags = text_input(stdscr, h//2 + 4, w//2 - 20, "KEYWORDS (comma sep):")
                        if tags:
                            cfg['classes'].append({"name": name, "tags": [t.strip() for t in tags.split(',') if t.strip()]})
                elif c:
                    cls = next((x for x in cfg['classes'] if x['name'] == c), None)
                    if cls:
                        act = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, f"MANAGE {c}", ["Edit Name", "Edit Tags", "Delete Class", "Cancel"])
                        if act == "Edit Name":
                            new_name = text_input(stdscr, h//2, w//2 - 20, "NEW NAME:", cls['name'])
                            if new_name: cls['name'] = new_name
                        elif act == "Edit Tags":
                            tags = text_input(stdscr, h//2, w//2 - 20, "TAGS (comma sep):", ",".join(cls['tags']))
                            if tags is not None: cls['tags'] = [t.strip() for t in tags.split(',') if t.strip()]
                        elif act == "Delete Class":
                            msg = f" DELETE CLASS '{c}'? (y/n) "
                            safe_addstr(stdscr, h-1, 2, " " * (w-3))
                            safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
                            stdscr.refresh()
                            stdscr.timeout(-1)
                            if stdscr.getch() in [ord('y'), ord('Y')]:
                                cfg['classes'].remove(cls)
                            stdscr.timeout(50)
            elif sel == 2:
                save_config(cfg)
                return 'HISTORY'
        elif k == 27: return 'HISTORY'

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
            header = f"{ ' DATE':<19} | { ' PROJ':<12} | { ' TASK':<20} | { ' DUR':<5} | { ' STATUS':<12} | {' MULT'}"
        else:
            header = f"{ 'DATE':<19} | {'PROJECT':<12} | {'TASK':<20} | {'DUR':<5} | {'STATUS':<12} | {'MULT'}"
        safe_addstr(stdscr, 2, 2, header, curses.color_pair(3)); safe_addstr(stdscr, 3, 2, "-"*min(len(header), w-2), curses.color_pair(3))
        list_h = max(1, h - 6)
        if not history: idx = 0
        else: idx = max(0, min(idx, len(history) - 1))
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
        safe_addstr(stdscr, h-1, 2, "[N] New  [L] Todo  [D] Del  [H] Heat  [W] Week  [R] Raid  [S] Set  [I] Info  [Q] Quit", curses.color_pair(4))
        draw_pip_timer(stdscr); stdscr.refresh(); k = stdscr.getch()
        if k == -1: continue
        nav = check_nav_keys(k); 
        if nav: return nav
        if k in [ord('n'), ord('N')]: return 'NEW'
        elif k in [ord('d'), ord('D')] and history: 
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
        btns = ["MENU", "RESTART", "QUIT"] if SESSION['state']=='finished' else ["PAUSE" if SESSION['state']=='running' else "RESUME", "STOP", "RESTART", "BACK", "QUIT"]
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
            elif sel == "QUIT": terminate_session(); return 'QUIT'
            elif sel == "STOP": terminate_session(); return 'HISTORY'
            elif sel == "RESTART": terminate_session(); start_new_session(SESSION['project'], SESSION['task'], SESSION['duration_secs']//60); return 'TIMER'
            elif sel == "RESUME": resume_timer()
            elif sel == "PAUSE": pause_timer()
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
        safe_addstr(stdscr, 1, 4, f"{total_c} contributions to the guild in the last year", curses.color_pair(1)|curses.A_BOLD)
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
        safe_addstr(stdscr, h-1, 2, "[L] Todo  PRESS [ESC] BACK", curses.color_pair(1))
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
        
        # Calculate Class
        top_p = max(proj_xp, key=proj_xp.get) if proj_xp else "Novice"
        p_class = determine_class(top_p)
        
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
        safe_addstr(stdscr, h-1, 2, "[L] Todo  [ESC] Return", curses.color_pair(9))
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
        safe_addstr(stdscr, h-1, 2, "[L] Todo  [Arrows] Select  [ESC] Retreat", curses.color_pair(1)|curses.A_BOLD)
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
        if y+2 < h-2: safe_addstr(stdscr, y+2, x+3, f"LVL 5 ([{'█'*10 + '░'*10}])", curses.color_pair(7))
        y += 5
        if y < h-2: safe_addstr(stdscr, y, x, "2. COMBAT: BUILD THE PILLARS", curses.color_pair(9)|curses.A_BOLD)
        if y+1 < h-2: safe_addstr(stdscr, y+1, x, "   Taller bars = More work done today.", curses.color_pair(1))
        if y+2 < h-2: safe_addstr(stdscr, y+2, x+3, "█  (Crit!)  ♛ > 2Hrs", curses.color_pair(7)|curses.A_BOLD)
        if y+3 < h-2: safe_addstr(stdscr, y+3, x+3, "▓  (High)", curses.color_pair(8))
        if y+4 < h-2: safe_addstr(stdscr, y+4, x+3, "▒  (Med)", curses.color_pair(8)|curses.A_DIM)
        y += 6
        if y < h-2: safe_addstr(stdscr, y, x, "3. CONTROLS", curses.color_pair(11)|curses.A_BOLD)
        keys = [("[N]","New"), ("[L]","Todo"), ("[T]","Timer"), ("[H]","Heatmap"), ("[W]","Dungeon"), ("[R]","Raid"), ("[D]","Delete"), ("[S]","Settings")]
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

PROJECT_COLORS_NAMES = ["Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White", "Crimson", "Lime", "Violet"]

def select_color(stdscr, y, x):
    sel = 0
    while True:
        draw_box(stdscr, y, x, 14, 20, "SELECT COLOR")
        for i, name in enumerate(PROJECT_COLORS_NAMES):
            attr = curses.A_REVERSE if i == sel else 0
            safe_addstr(stdscr, y+1+i, x+2, f" {name:<10}", attr | curses.color_pair(30+i))
        
        stdscr.refresh()
        k = stdscr.getch()
        
        if k == curses.KEY_UP: sel = max(0, sel-1)
        elif k == curses.KEY_DOWN: sel = min(len(PROJECT_COLORS_NAMES)-1, sel+1)
        elif k in [10, 13]: return 30 + sel # Return Color Pair ID
        elif k == 27: return None # Cancel

def add_new_todo_dialog(stdscr):
    h, w = stdscr.getmaxyx()
    content = text_input(stdscr, h//2 - 6, w//2 - 20, "TASK CONTENT (ESC to Cancel):")
    if content is None: return
    if not content.strip(): return
    
    today = datetime.now().strftime("%Y-%m-%d")
    d_str = text_input(stdscr, h//2 - 2, w//2 - 20, "DATE (ESC to Cancel):", today)
    if d_str is None: return
    if not d_str: d_str = today
    
    projs = ["General"] + get_unique_projects() + ["+ NEW PROJECT"]
    p = fuzzy_select(stdscr, h//2 + 2, w//2 - 20, "PROJECT (ESC to Cancel)", projs)
    if p is None: return
    
    new_proj_color = None
    if p == "+ NEW PROJECT":
        p = text_input(stdscr, h//2 + 2, w//2 - 20, "NEW PROJECT NAME:")
        if not p: return
        # Select Color for new project
        new_proj_color = select_color(stdscr, h//2 - 5, w//2 + 22)
    
    tags_str = text_input(stdscr, h//2 + 6, w//2 - 20, "TAGS (ESC to Cancel):")
    if tags_str is None: return
    tags = [t.strip() for t in tags_str.split(',')] if tags_str else []
    
    # Confirmation
    msg = " SAVE TASK? (y/n) "
    safe_addstr(stdscr, h-1, 2, " " * (w-3))
    safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.timeout(-1)
    k = stdscr.getch()
    stdscr.timeout(50)
    if k in [ord('y'), ord('Y')]:
        add_todo(content, d_str, p, tags)
        if new_proj_color:
             add_project(p, new_proj_color)

def show_backlog_view(stdscr):
    sel_idx = -1
    scroll_idx = 0
    
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        todos = load_todos()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Filter for past items only
        past_todos = [t for t in todos if t.get('date', '9999-99-99') < today_str]
        
        tree = []
        groups = {}
        for t in past_todos:
            d = t.get('date', 'Unknown')
            if d not in groups: groups[d] = []
            groups[d].append(t)
        
        # Sort by date descending (newest backlog first)
        sorted_keys = sorted(groups.keys(), reverse=True)
        
        # Build flattened tree
        selectable_indices = []
        curr_row = 0
        
        for k in sorted_keys:
            items = groups[k]
            # Add Header
            done_c = sum(1 for i in items if i['status']=='done')
            tree.append({'type': 'group', 'key': k, 'done': done_c, 'total': len(items)})
            curr_row += 1
            
            # Add Items
            for item in items:
                tree.append({'type': 'item', 'data': item})
                if item['status'] == 'pending':
                    selectable_indices.append(curr_row)
                curr_row += 1
        
        # Header
        safe_addstr(stdscr, 1, 2, "  BACKLOG REVIEW  ", curses.color_pair(5)|curses.A_BOLD|curses.A_REVERSE)
        safe_addstr(stdscr, 2, 2, "="*(w-4), curses.color_pair(5))
        
        list_h = h - 5
        
        # Auto-select first selectable if selection invalid
        if selectable_indices and (sel_idx < 0 or sel_idx not in selectable_indices):
            # Try to find nearest or default to first
            if sel_idx < 0: sel_idx = selectable_indices[0]
            else:
                # Find closest match
                sel_idx = min(selectable_indices, key=lambda x: abs(x-sel_idx))
        
        if not selectable_indices: sel_idx = -1
        
        # Scroll logic
        if sel_idx >= 0:
            if sel_idx < scroll_idx: scroll_idx = sel_idx
            elif sel_idx >= scroll_idx + list_h: scroll_idx = sel_idx - list_h + 1
        
        # Render
        if not tree:
            safe_addstr(stdscr, 4, 4, "No backlog items found!", curses.A_DIM)
        else:
            for i in range(list_h):
                ii = scroll_idx + i
                if ii >= len(tree): break
                node = tree[ii]
                is_sel = (ii == sel_idx)
                
                if node['type'] == 'group':
                    k = node['key']
                    try:
                        dt = datetime.strptime(k, "%Y-%m-%d")
                        lbl = dt.strftime("%a %d/%b/%Y").upper()
                    except: lbl = k
                    pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
                    safe_addstr(stdscr, 4+i, 2, f"[-] {lbl:<20} {pct:>3}% DONE", curses.color_pair(4)|curses.A_BOLD)
                else:
                    item = node['data']
                    st = "[x]" if item['status']=='done' else "[ ]"
                    
                    if item['status'] == 'done':
                        attr = curses.A_DIM
                        col = 0
                    else:
                        attr = curses.A_REVERSE if is_sel else 0
                        col = curses.color_pair(5) # Red for pending
                        
                    tags = f" {{{','.join(item.get('tags',[]))}}}" if item.get('tags') else ""
                    safe_addstr(stdscr, 4+i, 4, f"  {st} {item['content']}{tags}", attr|col)

        safe_addstr(stdscr, h-1, 2, "[Enter] Complete  [B/ESC] Return", curses.color_pair(4))
        stdscr.refresh()
        stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        
        if k == -1: time.sleep(0.05); continue
        
        nav = check_nav_keys(k)
        if nav: return nav
        
        if k in [ord('b'), ord('B'), 27]: return 'TODO'
        
        if not selectable_indices: continue
        
        if k in [curses.KEY_DOWN, ord('j')]:
            # Find next selectable index > sel_idx
            next_idxs = [x for x in selectable_indices if x > sel_idx]
            if next_idxs: sel_idx = next_idxs[0]
        elif k in [curses.KEY_UP, ord('k')]:
            # Find prev selectable index < sel_idx
            prev_idxs = [x for x in selectable_indices if x < sel_idx]
            if prev_idxs: sel_idx = prev_idxs[-1]
        elif k in [10, 13]: # Enter
             if 0 <= sel_idx < len(tree) and tree[sel_idx]['type'] == 'item':
                 toggle_todo(tree[sel_idx]['data']['id'])
                 # Don't move selection immediately, let next render loop handle state change (it will become unselectable)
                 # But we might want to auto-jump to next?
                 # Let's let the loop re-calculate selectable_indices. 
                 # If current sel_idx becomes invalid (completed), the auto-select logic at top of loop will pick nearest.

def show_todo_list(stdscr):
    mode = 'DAILY'
    expanded = set()
    sel_idx = 0
    scroll_idx = 0
    delete_pending_idx = -1
    jump_target = None
    
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        todos = load_todos()
        today_str = datetime.now().strftime("%Y-%m-%d")
        cfg = load_config()
        p_colors = cfg.get('project_colors', {})
        
        tree = []
        if mode == 'DAILY':
            groups = {}
            for t in todos:
                d = t.get('date', 'Unknown')
                if d not in groups: groups[d] = []
                groups[d].append(t)
            sorted_keys = sorted(groups.keys(), reverse=True)
            for k in sorted_keys:
                items = groups[k]
                done_c = sum(1 for i in items if i['status']=='done')
                tree.append({'type': 'group', 'key': k, 'items': items, 'done': done_c, 'total': len(items)})
                if k in expanded:
                    for item in items:
                        tree.append({'type': 'item', 'data': item, 'parent': k})
        else: # PROJECT MODE (Restructured: Project -> Date -> Task)
            p_groups = {}
            for t in todos:
                p = t.get('project', 'General') or "General"
                if p not in p_groups: p_groups[p] = []
                p_groups[p].append(t)
            
            sorted_projs = sorted(p_groups.keys(), key=lambda x: (0 if x=='General' else 1, x))
            
            for i_p, p in enumerate(sorted_projs):
                p_items = p_groups[p]
                
                # Project Level Stats
                done_p = sum(1 for i in p_items if i['status']=='done')
                is_last_proj = (i_p == len(sorted_projs) - 1)
                tree.append({'type': 'project', 'key': p, 'done': done_p, 'total': len(p_items), 'is_last': is_last_proj})
                
                if p in expanded:
                    # Group by Date inside Project
                    d_groups = {}
                    for t in p_items:
                        d = t.get('date', 'Unknown')
                        if d not in d_groups: d_groups[d] = []
                        d_groups[d].append(t)
                    
                    # Sort Dates (Today/Newest first)
                    sorted_dates = sorted(d_groups.keys(), reverse=True)
                    
                    for i_d, d in enumerate(sorted_dates):
                        d_items = sorted(d_groups[d], key=lambda x: x.get('content', '')) 
                        d_done = sum(1 for i in d_items if i['status']=='done')
                        d_key = f"{p}|{d}"
                        is_last_date = (i_d == len(sorted_dates) - 1)
                        
                        tree.append({'type': 'date_group', 'key': d_key, 'date': d, 'done': d_done, 'total': len(d_items), 'parent': p, 'is_last': is_last_date})
                        
                        if jump_target == d_key:
                             sel_idx = len(tree) - 1
                             jump_target = None
                        
                        if d_key in expanded:
                            for i_t, item in enumerate(d_items):
                                is_last_item = (i_t == len(d_items) - 1)
                                tree.append({'type': 'item', 'data': item, 'parent': d_key, 'is_last': is_last_item})

        # Tabs Header
        tabs = f" [DAILY] " if mode=='DAILY' else "  DAILY  "
        tabs += f" [PROJECT] " if mode=='PROJECT' else "  PROJECT  "
        safe_addstr(stdscr, 1, 2, tabs, curses.color_pair(3)|curses.A_BOLD)
        safe_addstr(stdscr, 2, 2, "="*(w-4), curses.color_pair(3))
        
        list_h = h - 5
        if not tree: sel_idx = 0
        else: sel_idx = max(0, min(sel_idx, len(tree)-1))
        
        if sel_idx < scroll_idx: scroll_idx = sel_idx
        elif sel_idx >= scroll_idx + list_h: scroll_idx = sel_idx - list_h + 1
        
        for i in range(list_h):
            ii = scroll_idx + i
            if ii >= len(tree): break
            node = tree[ii]
            is_sel = (ii == sel_idx)
            attr = curses.A_REVERSE if is_sel else 0
            
            # Render Logic
            if node['type'] == 'group': # DAILY Mode Header
                k = node['key']
                try:
                    dt = datetime.strptime(k, "%Y-%m-%d")
                    lbl = dt.strftime("%a %d/%b/%Y").upper()
                    if k == today_str: lbl = f"★ {lbl}"
                    else: lbl = f"  {lbl}"
                except: lbl = k
                pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
                icon = "[-]" if k in expanded else "[+]"
                safe_addstr(stdscr, 4+i, 2, f"{icon} {lbl:<25} {pct:>3}%", attr|curses.color_pair(4))
            
            elif node['type'] == 'project': # PROJECT Mode Top Level
                k = node['key']
                pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
                icon = "[-]" if k in expanded else "[+]"
                # Project Color
                col_id = p_colors.get(k, 3) # Default Blue
                try: col = curses.color_pair(col_id)
                except: col = curses.color_pair(3)
                
                safe_addstr(stdscr, 4+i, 2, f"{icon} {k:<25} {pct:>3}%", attr|col|curses.A_BOLD)
                
            elif node['type'] == 'date_group': # PROJECT Mode Date Sub-Level
                d = node['date']
                p_name = node['parent']
                try:
                    dt = datetime.strptime(d, "%Y-%m-%d")
                    lbl = dt.strftime("%a %d/%b/%Y").upper()
                    if d == today_str: lbl = f"★ {lbl}"
                    else: lbl = f"  {lbl}"
                except: lbl = d
                
                pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
                
                # Tree lines
                col_id = p_colors.get(p_name, 3)
                try: col = curses.color_pair(col_id)
                except: col = curses.color_pair(3)
                
                # Check backlog (past incomplete) for dashes
                is_backlog = d < today_str and node['done'] < node['total']
                line_char = "├─" if not node['is_last'] else "└─"
                if is_backlog: line_char = "├╌" if not node['is_last'] else "└╌"
                
                safe_addstr(stdscr, 4+i, 2, f"  {line_char}", col)
                safe_addstr(stdscr, 4+i, 6, f"{lbl:<23} {pct:>3}%", attr|curses.color_pair(4))

            elif node['type'] == 'item':
                item = node['data']
                st = "[x]" if item['status']=='done' else "[ ]"
                col = curses.color_pair(2) if item['status']=='done' else 0
                tags = f" {{{','.join(item.get('tags',[]))}}}" if item.get('tags') else ""
                
                prefix = ""
                indent = 4
                
                if mode == 'DAILY':
                    indent = 4
                    # Use Project Color for task text in Daily View
                    p_name = item.get('project')
                    if p_name and p_name != "General":
                         col_id = p_colors.get(p_name, 0)
                         if col_id and not item['status']=='done':
                             try: col = curses.color_pair(col_id)
                             except: pass
                    
                    # Backlog dashes
                    if item.get('date', '9999') < today_str and item['status'] == 'pending':
                         prefix = "╌╌ "
                    else:
                         prefix = "   "
                         
                else: # PROJECT Mode
                    indent = 6
                    # Tree lines for tasks
                    p_name = node.get('parent', '').split('|')[0]
                    col_id = p_colors.get(p_name, 3)
                    try: tree_col = curses.color_pair(col_id)
                    except: tree_col = curses.color_pair(3)
                    
                    line_char = "│  ├─" if not node.get('is_last') else "│  └─"
                    # We need to know if parent date group was last to decide if we draw vertical bar
                    # Simplified for TUI:
                    safe_addstr(stdscr, 4+i, 2, line_char, tree_col)
                    prefix = ""
                
                safe_addstr(stdscr, 4+i, indent, f"{prefix}{st} {item['content']}{tags}", attr|col)
                
            if ii == delete_pending_idx:
                safe_addstr(stdscr, 4+i, w-25, " PRESS 'D' AGAIN TO DELETE ", curses.color_pair(5)|curses.A_BOLD|curses.A_REVERSE)
        
        safe_addstr(stdscr, h-1, 2, "[TAB] View  [N] New  [Enter] Toggle  [B] Backlog  [D] Del  [U] Undo  [ESC] Back", curses.color_pair(4))
        stdscr.refresh()
        stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        
        if k == -1: time.sleep(0.05); continue
        
        nav = check_nav_keys(k)
        if nav and nav != 'TODO': return nav
        
        if k in [ord('b'), ord('B')]:
            res = show_backlog_view(stdscr)
            if res != 'TODO': return res
            
        if k in [ord('u'), ord('U')]:
             restore_last_deleted_item()
             delete_pending_idx = -1
        
        if k == 9:
            mode = 'PROJECT' if mode == 'DAILY' else 'DAILY'
            expanded = set()
            sel_idx = 0; scroll_idx = 0; delete_pending_idx = -1
        elif k in [curses.KEY_DOWN, ord('j')]: 
            sel_idx += 1; delete_pending_idx = -1
        elif k in [curses.KEY_UP, ord('k')]: 
            sel_idx -= 1; delete_pending_idx = -1
        elif k in [10, 13]:
            if tree:
                node = tree[sel_idx]
                if node['type'] in ['group', 'project', 'date_group']:
                    key = node['key']
                    if key in expanded: expanded.remove(key)
                    else: 
                        expanded.add(key)
                        if node['type'] == 'project':
                            today_key = f"{key}|{today_str}"
                            expanded.add(today_key)
                            jump_target = today_key
                else:
                    toggle_todo(node['data']['id'])
            delete_pending_idx = -1
        elif k in [ord('n'), ord('N')]:
            add_new_todo_dialog(stdscr); delete_pending_idx = -1
        elif k in [ord('d'), ord('D')]:
            if tree:
                if delete_pending_idx == sel_idx:
                     node = tree[sel_idx]
                     if node['type'] == 'item':
                         delete_todo(node['data']['id'])
                     delete_pending_idx = -1
                else:
                     node = tree[sel_idx]
                     if node['type'] == 'item':
                         delete_pending_idx = sel_idx
        elif k == 27: return 'HISTORY'

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
    # Basic UI Colors
    for i, c in enumerate([curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_YELLOW], 1): curses.init_pair(i, c, -1)
    
    # Project Colors (IDs 30-39)
    # Mapping roughly to: Red, Green, Yellow, Blue, Magenta, Cyan, White, Bright Red, Bright Green, Bright Yellow
    project_colors = [
        curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_BLUE, 
        curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE, 160, 46, 226
    ]
    # Fallback for standard terminals
    std_colors = [curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE, curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW]
    
    for i in range(10):
        c = project_colors[i] if curses.can_change_color() and i < len(project_colors) else std_colors[i]
        try: curses.init_pair(30+i, c, -1)
        except: curses.init_pair(30+i, std_colors[i], -1)

    curses.curs_set(0); view = 'HISTORY'
    while True:
        if view == 'HISTORY': view = show_history(stdscr)
        elif view == 'TIMER': view = show_timer_view(stdscr)
        elif view == 'HEATMAP': view = show_yearly_heatmap(stdscr)
        elif view == 'WEEKLY': view = show_weekly_dungeon(stdscr)
        elif view == 'RAID': view = show_daily_raid(stdscr)
        elif view == 'INFO': view = show_info_screen(stdscr)
        elif view == 'SETTINGS': view = show_settings(stdscr)
        elif view == 'TODO': view = show_todo_list(stdscr)
        elif view == 'NEW':
            stdscr.erase(); h, w = stdscr.getmaxyx()
            p = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "PROJECT", get_unique_projects())
            if not p: view = 'HISTORY'; continue
            
            # Merge pending todos + history tasks
            pending_todos = [t['content'] for t in load_todos() if t.get('project') == p and t.get('status') == 'pending']
            history_tasks = get_unique_tasks(p)
            # Remove duplicates from history that are in pending
            history_tasks = [t for t in history_tasks if t not in pending_todos]
            
            # Display pending with a star indicator (visual only? No, just list them first)
            # If we add visual indicator, fuzzy_select needs to return the clean value.
            # For simplicity, we just list them first. The user knows they are likely todos.
            
            all_tasks = pending_todos + history_tasks
            
            t = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "TASK", all_tasks)
            if not t: view = 'HISTORY'; continue
            d = select_duration(stdscr)
            if not d: view = 'HISTORY'; continue
            start_new_session(p, t, d); view = 'TIMER'
        elif view == 'QUIT':
            if SESSION['active']: terminate_session()
            break

if __name__ == "__main__":
    try: curses.wrapper(main)
    except KeyboardInterrupt: print("\nExited.")
