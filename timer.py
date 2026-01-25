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
            break
    
    if not target: return

    if target['status'] == 'pending':
        # Switch to DONE
        target['status'] = 'done'
        
        # Create a history entry with ID for tracking
        sess_id = str(uuid.uuid4())
        session = {
            "id": sess_id,
            "project": target.get('project', 'General'),
            "task": target.get('content', 'Unknown'),
            "duration_minutes": 30,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "manual_log": True
        }
        save_session(session)
        target['last_session_id'] = sess_id
        
    else:
        # Switch back to PENDING
        target['status'] = 'pending'
        
        # Remove the auto-added session if it exists
        sid = target.get('last_session_id')
        if sid:
            history = load_history()
            new_history = [h for h in history if h.get('id') != sid]
            if len(history) != len(new_history):
                with open(DATA_FILE, 'w') as f: json.dump(new_history, f, indent=2)
            # Remove the link
            del target['last_session_id']
            
    save_todos(todos)

def delete_todo(todo_id):
    todos = load_todos()
    item = next((t for t in todos if t['id'] == todo_id), None)
    if item:
        UNDO_STACK.append({'type': 'todo', 'data': item})
        todos = [t for t in todos if t['id'] != todo_id]
        save_todos(todos)

def add_project(name, color_id=None, tags=None):
    if not name: return
    cfg = load_config()
    
    # Always ensure the key exists, even if tags is empty
    if name not in cfg['project_tags']:
        cfg['project_tags'][name] = tags if tags else []
    elif tags: 
        # If project exists and we provided tags, merge/overwrite? 
        # For new project flow, it shouldn't exist. If it does, we probably just want to update colors/tags?
        # Let's simple append for safety or overwrite if empty.
        # But per requirements "project tags should be assigned per task" (creation flow), 
        # this implies defining them. Let's just set them if provided.
        cfg['project_tags'][name] = tags

    if color_id:
            if 'project_colors' not in cfg: cfg['project_colors'] = {}
            cfg['project_colors'][name] = color_id
    save_config(cfg)

def delete_project(name):
    if name == "General": return # Protect General
    
    # 1. Remove from Config
    cfg = load_config()
    if name in cfg['project_tags']:
        # Undo only covers config restoration, not data
        col = cfg.get('project_colors', {}).get(name)
        UNDO_STACK.append({'type': 'project', 'data': {'name': name, 'tags': cfg['project_tags'][name], 'color': col}})
        del cfg['project_tags'][name]
        if 'project_colors' in cfg and name in cfg['project_colors']:
            del cfg['project_colors'][name]
        save_config(cfg)
    
    # 2. Remove from Todos
    todos = load_todos()
    new_todos = [t for t in todos if t.get('project') != name]
    if len(todos) != len(new_todos):
        save_todos(new_todos)

    # 3. Remove from History
    history = load_history()
    new_history = [h for h in history if h.get('project') != name]
    if len(history) != len(new_history):
        with open(DATA_FILE, 'w') as f: json.dump(new_history, f, indent=2)

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
                while True:
                    projs = get_unique_projects() + ["+ ADD NEW PROJECT"]
                    p = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "SELECT PROJECT", projs)
                    if not p: break

                    if p == "+ ADD NEW PROJECT":
                        new_p = text_input(stdscr, h//2, w//2 - 20, "PROJECT NAME:")
                        if new_p: add_project(new_p); cfg = load_config()
                    elif p:
                        act = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, f"MANAGE {p}", ["Edit Tags", "Edit Color", "Delete Project", "Cancel"])
                        if act == "Edit Tags":
                            curr_tags = cfg['project_tags'].get(p, [])
                            val = text_input(stdscr, h//2, w//2 - 20, f"TAGS FOR '{p}' (comma sep):", ",".join(curr_tags))
                            if val is not None:
                                cfg['project_tags'][p] = [t.strip() for t in val.split(',') if t.strip()]
                                save_config(cfg)
                        elif act == "Edit Color":
                            # Current color
                            c_id = cfg.get('project_colors', {}).get(p)
                            new_col = select_color(stdscr, h//2 - 5, w//2 + 22)
                            if new_col:
                                if 'project_colors' not in cfg: cfg['project_colors'] = {}
                                cfg['project_colors'][p] = new_col
                                save_config(cfg)
                        elif act == "Delete Project":
                            msg = f" PERMANENTLY DELETE '{p}' + DATA? (y/n) "
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
    cfg = load_config()
    
    view_mode = 'TODAY' # 'TODAY' or 'ALL'
    current_date = datetime.now().date()
    
    while True:
        tick_timer()
        if time.time() - last_load > 1.0: history = load_history(); last_load = time.time()
        stdscr.erase(); h, w = stdscr.getmaxyx()
        
        # Filter History based on Mode
        display_history = []
        if view_mode == 'ALL':
            display_history = history
            title_str = "ALL HISTORY"
        else:
            display_history = [
                x for x in history 
                if x.get('timestamp') and datetime.fromisoformat(x['timestamp']).date() == current_date
            ]
            title_str = f"HISTORY: {current_date.strftime('%a %d %b %Y').upper()}"

        tt, ty, ratio = calculate_stats()
        r_str = f"{ratio:.2f}x" if ratio != float('inf') else "INF"
        
        # Header
        safe_addstr(stdscr, 0, 2, f"{title_str:<30} | TODAY: {tt:.1f}m | YEST: {ty:.1f}m", curses.color_pair(2)|curses.A_BOLD)
        
        # Table Header
        if use_nerd:
            header = f"{ ' TIME':<6} | { ' PROJECT':<12} | { ' TASK':<25} | { ' DUR':<5} | { ' STATUS':<10} | {' MULT'}"
        else:
            header = f"{ 'TIME':<6} | {'PROJECT':<12} | {'TASK':<25} | {'DUR':<5} | {'STATUS':<10} | {'MULT'}"
        safe_addstr(stdscr, 2, 2, header, curses.color_pair(3)); safe_addstr(stdscr, 3, 2, "-"*min(len(header), w-2), curses.color_pair(3))
        
        list_h = max(1, h - 6)
        if not display_history: idx = 0
        else: idx = max(0, min(idx, len(display_history) - 1))
        
        if idx < scroll: scroll = idx
        elif idx >= scroll + list_h: scroll = idx - list_h + 1
        
        # Table Content
        if not display_history:
            safe_addstr(stdscr, 4, 2, "No sessions found for this period.", curses.A_DIM)
        else:
            p_colors = cfg.get('project_colors', {})
            for i in range(list_h):
                ii = scroll + i
                if ii >= len(display_history): break
                it = display_history[ii]; st = "SUCCESS" if it.get('status')=='completed' else "TERM"
                dm = f"{it.get('duration_minutes',0)}m" if st=="SUCCESS" else f"{int(it.get('actual_duration_seconds',0)//60)}m"
                
                # Extract HH:MM
                ts = it.get('timestamp', '')
                tm_str = ts[11:16] if len(ts) >= 16 else "--:--"
                
                # Project Color logic
                p_name = it.get('project', '-')
                p_color_id = p_colors.get(p_name, 0)
                
                if use_nerd: st = " SUCCESS" if st=="SUCCESS" else " TERM"
                
                # Selection vs Row attribute
                if ii == idx:
                    attr = curses.color_pair(p_color_id or 1) | curses.A_REVERSE
                else:
                    attr = curses.color_pair(p_color_id) if p_color_id else 0
                
                # Row content
                row_str = f"{tm_str:<6} | {p_name[:12]:<12} | {it.get('task','-')[:25]:<25} | {dm:<5} | {st[:10]:<10} | {'1.0x' if st.endswith('SUCCESS') else '-'}"
                safe_addstr(stdscr, 4+i, 2, row_str, attr)
        
        # Footer Help
        nav_help = "[TAB] View  [[] Day -  []] Day +  [N] New  [L] Todo  [D] Del"
        safe_addstr(stdscr, h-1, 2, f"{nav_help}  [H] Heat  [W] Week  [R] Raid  [S] Set  [Q] Quit", curses.color_pair(4))
        
        draw_pip_timer(stdscr); stdscr.refresh(); k = stdscr.getch()
        if k == -1: continue
        nav = check_nav_keys(k); 
        if nav: return nav
        
        if k == 9: # TAB
            view_mode = 'ALL' if view_mode == 'TODAY' else 'TODAY'
            idx = 0; scroll = 0
        elif k in [ord('['), curses.KEY_SLEFT]: # Prev Day
            current_date -= timedelta(days=1)
            view_mode = 'TODAY'; idx = 0; scroll = 0
        elif k in [ord(']'), curses.KEY_SRIGHT]: # Next Day
            if current_date < datetime.now().date():
                current_date += timedelta(days=1)
                view_mode = 'TODAY'; idx = 0; scroll = 0
        elif k in [ord('n'), ord('N')]: return 'NEW'
        elif k in [ord('d'), ord('D')] and display_history: 
            msg = " DELETE SESSION? (y/n) "
            safe_addstr(stdscr, h-1, 2, " " * (w-3))
            safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
            stdscr.refresh()
            stdscr.timeout(-1)
            conf_k = stdscr.getch()
            stdscr.timeout(50)
            if conf_k in [ord('y'), ord('Y')]:
                target_item = display_history[idx]
                real_idx = -1
                for ri, rh in enumerate(history):
                    if rh == target_item:
                        real_idx = ri; break
                if real_idx != -1:
                    delete_session(real_idx); history = load_history()
        elif k in [ord('q'), ord('Q')]: return 'QUIT'
        elif k == curses.KEY_UP: idx -= 1
        elif k == curses.KEY_DOWN: idx += 1

def show_timer_view(stdscr):
    btn = 0
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx()
        if not SESSION['active']: return 'HISTORY'
        
        cfg = load_config()
        p_color_id = cfg.get('project_colors', {}).get(SESSION['project'], 0)
        p_attr = curses.color_pair(p_color_id) if p_color_id else 0
        
        draw_box(stdscr, 1, 2, 6, max(40, w - 35), "DETAILS")
        safe_addstr(stdscr, 2, 4, f"PROJECT: {SESSION['project']}", p_attr|curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, f"TASK:    {SESSION['task']}")
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
            ss = todays[sel]; sy = 5; x = split+2
            
            cfg = load_config()
            p_color_id = cfg.get('project_colors', {}).get(ss.get('project'), 0)
            p_attr = curses.color_pair(p_color_id) if p_color_id else curses.color_pair(12)
            
            safe_addstr(stdscr, sy, x, f"QUEST: {ss.get('project','-')}", p_attr|curses.A_BOLD)
            safe_addstr(stdscr, sy+1, x, f"OBJ:   {ss.get('task','-')}", curses.color_pair(1))
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
    new_proj_tags = []
    
    if p == "+ NEW PROJECT":
        p = text_input(stdscr, h//2 + 2, w//2 - 20, "NEW PROJECT NAME:")
        if not p: return
        
        # Project Tags
        p_tags_str = text_input(stdscr, h//2 + 4, w//2 - 20, "PROJECT TAGS (comma sep):")
        if p_tags_str is None: return
        new_proj_tags = [t.strip() for t in p_tags_str.split(',')] if p_tags_str else []
        
        # Select Color for new project
        curses.flushinp()
        new_proj_color = select_color(stdscr, h//2 - 5, w//2 + 22)
    
    tags_str = text_input(stdscr, h//2 + 6, w//2 - 20, "TASK TAGS (ESC to Cancel):")
    if tags_str is None: return
    tags = [t.strip() for t in tags_str.split(',')] if tags_str else []
    
    # Confirmation
    msg = " SAVE TASK? (y/n/Enter) "
    safe_addstr(stdscr, h-1, 2, " " * (w-3))
    safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.timeout(-1)
    k = stdscr.getch()
    stdscr.timeout(50)
    if k in [ord('y'), ord('Y'), 10, 13]:
        add_todo(content, d_str, p, tags)
        if new_proj_color or new_proj_tags or p not in projs:
             # Even if no color/tags, we need to save the new project entry
             add_project(p, new_proj_color, new_proj_tags)
        return p
    return None



def show_todo_list(stdscr):
    mode = 'DAILY'
    backlog_active = False
    isolation_filter = None # Key to filter by
    isolation_type = None   # 'project', 'date', 'date_group'
    expanded = set()
    sel_idx = 0
    scroll_idx = 0
    delete_pending_idx = -1
    jump_target = None
    
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        all_todos = load_todos()
        today_str = datetime.now().strftime("%Y-%m-%d")
        cfg = load_config()
        p_colors = cfg.get('project_colors', {})
        
        # 1. Apply Isolation Filter
        if isolation_filter:
            if isolation_type == 'project':
                todos = [t for t in all_todos if t.get('project') == isolation_filter]
            elif isolation_type == 'date': # Daily View Date
                todos = [t for t in all_todos if t.get('date') == isolation_filter]
            elif isolation_type == 'date_group': # Project|Date
                p_name, d_val = isolation_filter.split('|')
                todos = [t for t in all_todos if t.get('project') == p_name and t.get('date') == d_val]
            else:
                todos = all_todos
        else:
            todos = all_todos

        # 2. Apply Backlog Filter (on top of isolation)
        if backlog_active:
            todos = [t for t in todos if t.get('date', '9999-99-99') <= today_str]

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
                # In isolation mode, auto-expand the single root logic or just respect expanded
                # If isolated by date, we only have one group, so auto-expand it?
                # Let's respect standard expanded logic but maybe default expand if isolated?
                if k in expanded or (isolation_filter and isolation_type == 'date'):
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
                
                # Auto-expand if isolated by project
                is_isolated_proj = (isolation_filter == p and isolation_type == 'project')
                
                if p in expanded or is_isolated_proj:
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
                        
                        # Auto-expand if isolated by specific date_group
                        is_isolated_dg = (isolation_filter == d_key and isolation_type == 'date_group')
                        
                        if d_key in expanded or is_isolated_dg:
                            for i_t, item in enumerate(d_items):
                                is_last_item = (i_t == len(d_items) - 1)
                                tree.append({'type': 'item', 'data': item, 'parent': d_key, 'is_last': is_last_item, 'parent_last': is_last_date})

        # Tabs Header
        tabs = f" [DAILY] " if mode=='DAILY' else "  DAILY  "
        tabs += f" [PROJECT] " if mode=='PROJECT' else "  PROJECT  "
        safe_addstr(stdscr, 1, 2, tabs, curses.color_pair(3)|curses.A_BOLD)
        
        # Backlog Indicator
        indicator_x = 25
        if backlog_active:
            safe_addstr(stdscr, 1, indicator_x, " [BACKLOG VIEW] ", curses.color_pair(5)|curses.A_BOLD|curses.A_REVERSE)
            indicator_x += 17
            
        # Isolation Indicator
        if isolation_filter:
            iso_label = isolation_filter
            iso_col = 0
            if isolation_type == 'project':
                iso_col = p_colors.get(isolation_filter, 0)
            elif isolation_type == 'date_group':
                p_part = isolation_filter.split('|')[0]
                iso_col = p_colors.get(p_part, 0)
                iso_label = p_part # Shorten display
            
            # Use project color reversed (Background color + Dark Text ideally, or just Reverse)
            # Standard curses doesn't easily do "Dark Text on Bright BG" without defining new pairs.
            # We will use A_REVERSE with the project color.
            iso_attr = curses.color_pair(iso_col)|curses.A_REVERSE if iso_col else curses.A_REVERSE
            safe_addstr(stdscr, 1, indicator_x, f" [ISOLATED: {iso_label}] ", iso_attr|curses.A_BOLD)
            
        safe_addstr(stdscr, 2, 2, "="*(w-4), curses.color_pair(3))
        
        list_h = h - 5
        if not tree: 
            sel_idx = 0
            safe_addstr(stdscr, 4, 4, "No tasks found.", curses.A_DIM)
        else: sel_idx = max(0, min(sel_idx, len(tree)-1))
        
        if sel_idx < scroll_idx: scroll_idx = sel_idx
        elif sel_idx >= scroll_idx + list_h: scroll_idx = sel_idx - list_h + 1
        
        for i in range(list_h):
            ii = scroll_idx + i
            if ii >= len(tree): break
            node = tree[ii]
            is_sel = (ii == sel_idx)
            attr = curses.A_REVERSE if is_sel else 0
            
            # Margin Asterisk Logic
            show_asterisk = False
            ast_color = 5 # Default Red
            
            if node['type'] == 'item':
                if node['data']['status'] == 'pending': 
                    show_asterisk = True
                    p_name = node['data'].get('project', 'General')
                    ast_color = p_colors.get(p_name, 5)
            elif node['type'] == 'project':
                if node['done'] < node['total']:
                    show_asterisk = True
                    ast_color = p_colors.get(node['key'], 5)
            elif node['type'] == 'date_group':
                if node['done'] < node['total']:
                    show_asterisk = True
                    ast_color = p_colors.get(node['parent'], 5)
            elif node['type'] == 'group': # Daily View Date
                if node['done'] < node['total']:
                    show_asterisk = True
                    ast_color = 5 # Keep Red for overdue days
            
            if show_asterisk:
                try: col_pair = curses.color_pair(ast_color)
                except: col_pair = curses.color_pair(5)
                safe_addstr(stdscr, 4+i, 0, "\U0001F7BA", col_pair)

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
                icon = "[-]" if k in expanded or (isolation_filter and isolation_type=='date') else "[+]"
                
                # Check for overdue pending tasks
                is_past = k < today_str
                has_pending = node['done'] < node['total']
                header_attr = curses.color_pair(5)|curses.A_BOLD if (is_past and has_pending) else curses.color_pair(4)
                
                safe_addstr(stdscr, 4+i, 2, f"{icon} {lbl:<25} {pct:>3}%", attr|header_attr)
            
            elif node['type'] == 'project': # PROJECT Mode Top Level
                k = node['key']
                pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
                
                # Auto-open if isolated
                is_open = k in expanded or (isolation_filter == k and isolation_type == 'project')
                icon = "[-]" if is_open else "[+]"
                
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
                line_char = "  ├─" if not node['is_last'] else "  └─"
                if is_backlog: line_char = "  ├╌" if not node['is_last'] else "  └╌"
                
                date_attr = curses.color_pair(5)|curses.A_BOLD if is_backlog else curses.color_pair(4)
                
                safe_addstr(stdscr, 4+i, 2, f"{line_char}", col)
                safe_addstr(stdscr, 4+i, 6, f"{lbl:<23} {pct:>3}%", attr|date_attr)

            elif node['type'] == 'item':
                item = node['data']
                st = "[x]" if item['status']=='done' else "[ ]"
                
                # Determine Color
                is_overdue = (item.get('date', '9999-99-99') < today_str) and (item['status'] == 'pending')
                
                if item['status'] == 'done':
                    col = curses.color_pair(2) # Green
                elif is_overdue:
                    col = curses.color_pair(5) # Red for overdue
                else:
                    col = 0 # Default

                tags = f" {{{','.join(item.get('tags',[]))}}}" if item.get('tags') else ""
                
                prefix = ""
                indent = 4
                
                if mode == 'DAILY':
                    indent = 4
                    # Use Project Color for task text in Daily View (if not overdue/done)
                    p_name = item.get('project', 'General')
                    if p_name and p_name != "General" and not is_overdue and item['status'] != 'done':
                         col_id = p_colors.get(p_name, 0)
                         if col_id:
                             try: col = curses.color_pair(col_id)
                             except: pass
                    
                    # Backlog dashes
                    if is_overdue: prefix = "╌╌ "
                    else: prefix = "   "
                    
                    item_str = f"{prefix}{st} {p_name}: {item['content']}{tags}"
                         
                else: # PROJECT Mode
                    indent = 6
                    # Tree lines for tasks
                    p_name = node.get('parent', '').split('|')[0]
                    col_id = p_colors.get(p_name, 3)
                    try: tree_col = curses.color_pair(col_id)
                    except: tree_col = curses.color_pair(3)
                    
                    v_bar = "│" if not node.get('parent_last') else " "
                    branch = "├" if not node.get('is_last') else "└"
                    h_line = "─"
                    
                    # Dashed line for pending items
                    if item['status'] == 'pending':
                         h_line = "╌"
                    
                    line_str = f"  {v_bar}  {branch}{h_line}"
                    
                    safe_addstr(stdscr, 4+i, 2, line_str, tree_col)
                    indent = 9
                    item_str = f"{st} {item['content']}{tags}"
                
                safe_addstr(stdscr, 4+i, indent, item_str, attr|col)
                
            if ii == delete_pending_idx:
                safe_addstr(stdscr, 4+i, w-25, " PRESS 'D' AGAIN TO DELETE ", curses.color_pair(5)|curses.A_BOLD|curses.A_REVERSE)
        
        nav_hint = "[TAB] View  [B] Backlog: " + ("ON " if backlog_active else "OFF")
        safe_addstr(stdscr, h-1, 2, f"{nav_hint}  [E/C] Exp/Col All  [I] Isolate  [N] New  [Enter] Toggle  [D] Del  [U] Undo  [ESC] Back", curses.color_pair(4))
        stdscr.refresh()
        stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        
        if k == -1: time.sleep(0.05); continue
        
        nav = check_nav_keys(k)
        if nav and nav != 'TODO' and nav != 'INFO': return nav
        
        if k in [ord('e'), ord('E')]:
            if mode == 'DAILY':
                expanded.update(set(t.get('date', 'Unknown') for t in todos))
            else:
                for t in todos:
                    p = t.get('project', 'General') or 'General'
                    expanded.add(p)
                    expanded.add(f"{p}|{t.get('date', 'Unknown')}")
        elif k in [ord('c'), ord('C')]:
            expanded.clear()
        
        if k in [ord('b'), ord('B')]:
            backlog_active = not backlog_active
            # Don't clear isolation, just re-apply backlog filtering
            expanded = set()
            sel_idx = 0; scroll_idx = 0; delete_pending_idx = -1
            
        if k in [ord('i'), ord('I')]:
            if tree:
                node = tree[sel_idx]
                if node['type'] == 'group': # Date in Daily
                    if isolation_filter == node['key']: # Toggle off
                        isolation_filter = None; isolation_type = None
                    else:
                        isolation_filter = node['key']; isolation_type = 'date'
                elif node['type'] == 'project':
                    if isolation_filter == node['key']:
                        isolation_filter = None; isolation_type = None
                    else:
                        isolation_filter = node['key']; isolation_type = 'project'
                elif node['type'] == 'date_group':
                    if isolation_filter == node['key']:
                        isolation_filter = None; isolation_type = None
                    else:
                        isolation_filter = node['key']; isolation_type = 'date_group'
                
                # Reset view state slightly
                sel_idx = 0; scroll_idx = 0; delete_pending_idx = -1
            
        if k in [ord('u'), ord('U')]:
             restore_last_deleted_item()
             delete_pending_idx = -1
        
        if k == 9: # TAB
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
            new_p = add_new_todo_dialog(stdscr); delete_pending_idx = -1
            if new_p:
                mode = 'PROJECT'
                expanded.add(new_p)
                expanded.add(f"{new_p}|{today_str}")
                jump_target = f"{new_p}|{today_str}"
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
        elif k == 27:
            if isolation_filter:
                isolation_filter = None; isolation_type = None
                sel_idx = 0; scroll_idx = 0
            else:
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
    # Basic UI Colors
    for i, c in enumerate([curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_YELLOW], 1): curses.init_pair(i, c, -1)
    
    # Project Colors (IDs 30-39)
    # Use Fixed Xterm-256 Color Codes to bypass terminal themes
    # These indices (16-255) are standard and usually not overridden by color schemes.
    # Order: Red, Green, Yellow, Blue, Magenta, Cyan, White, Orange, Lime, Violet
    xterm_256_map = [
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
    
    # Fallback standard colors for terminals that might not support 256 colors (e.g. very old ones)
    std_colors = [
        curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_BLUE, 
        curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE, 
        curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_MAGENTA
    ]
    
    for i in range(10):
        pair_id = 30 + i
        # Try to use 256 colors if the terminal supports them (COLORS > 200)
        # Most modern terminals (Alacritty, Kitty, iTerm, Gnome) support 256.
        if curses.COLORS > 200:
            curses.init_pair(pair_id, xterm_256_map[i], -1)
        else:
            curses.init_pair(pair_id, std_colors[i], -1)

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
