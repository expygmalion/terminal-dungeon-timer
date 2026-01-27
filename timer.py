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

TODO_STATE = {
    'expanded_daily': set(),
    'expanded_project': set(),
    'mode': 'DAILY',
    'backlog_active': False,
    'isolation_filter': None,
    'isolation_type': None,
    'active_filter': None,
    'focus_queue': []
}

# --- Data Management ---
def load_todos():
    if not os.path.exists(TODO_FILE): return []
    try:
        with open(TODO_FILE, 'r') as f: return json.load(f)
    except: return []

def save_todos(todos):
    with open(TODO_FILE, 'w') as f: json.dump(todos, f, indent=2)

def clean_tags(tags):
    if not tags: return []
    return sorted(list(set(t.strip().upper() for t in tags if t and t.strip())))

def add_todo(content, date_str, project, tags, description=""):
    todos = load_todos()
    new_todo = {
        "id": str(uuid.uuid4()),
        "content": content,
        "description": description,
        "date": date_str,
        "project": project if project else "General",
        "tags": clean_tags(tags),
        "status": "pending",
        "focused": False,
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

def toggle_todo(todo_id, duration_mins=30):
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
            "duration_minutes": duration_mins,
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

def get_project_tags(project_name):
    cfg = load_config()
    return cfg.get('project_tags', {}).get(project_name, [])

def get_unique_projects():
    todos = load_todos()
    proj_map = {} # project -> latest_timestamp
    for t in todos:
        p = t.get('project', 'General')
        ts = t.get('timestamp', '')
        if p not in proj_map or ts > proj_map[p]:
            proj_map[p] = ts
    
    # Sort by timestamp descending
    sorted_p = sorted(proj_map.keys(), key=lambda x: proj_map[x], reverse=True)
    
    # Ensure General is always present
    if "General" not in sorted_p: sorted_p.append("General")
    
    return sorted_p

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
    h, w = stdscr.getmaxyx()
    
    proj = SESSION['project']
    task = SESSION['task']
    xp = SESSION['duration_secs'] // 60
    
    width = max(30, min(w-4, len(task) + 4), min(w-4, len(proj) + 15))
    height = 5
    
    y = h - 6
    x = (w - width) // 2
    
    if y < 0: return

    if SESSION['state'] == 'running': elapsed = SESSION['elapsed_before_pause'] + (time.time() - SESSION['start_time'])
    else: elapsed = SESSION['elapsed_before_pause']
    rem = max(0, SESSION['duration_secs'] - elapsed); t_str = format_duration(rem)
    
    color = curses.color_pair(4)
    if SESSION['state'] == 'paused': color = curses.color_pair(6)
    elif SESSION['state'] == 'finished': color = curses.color_pair(2)
    
    try:
        draw_box(stdscr, y, x, height, width, "ACTIVE TIMER")
        
        header = f"{proj[:20]} | {int(xp)} XP"
        safe_addstr(stdscr, y+1, x+2, header, curses.A_BOLD | curses.color_pair(2))
        
        safe_addstr(stdscr, y+2, x+2, task[:width-4])
        
        icon = "▶" if SESSION['state']=='running' else ("⏸" if SESSION['state']=='paused' else "✔")
        safe_addstr(stdscr, y+3, x + (width - len(t_str) - 4)//2, f"{icon} {t_str}", color | curses.A_BOLD)
    except: pass

def check_nav_keys(key):
    if key in [ord('h'), ord('H')]: return 'HEATMAP'
    if key in [ord('w'), ord('W')]: return 'WEEKLY'
    if key in [ord('r'), ord('R')]: return 'RAID'
    if key in [ord('i'), ord('I')]: return 'INFO'
    if key in [ord('p'), ord('P')]: return 'SETTINGS'
    if key in [ord('t'), ord('T')]: return 'TIMER'
    if key in [ord('l'), ord('L')]: return 'TODO'
    return None

def is_subsequence(q, t):
    it = iter(t.lower()); q = q.lower().replace(" ", "")
    return all(c in it for c in q)

def text_input(stdscr, y, x, prompt, prefill=""):
    query = prefill
    stdscr.nodelay(True)
    while True:
        # Render prompt + current query
        safe_addstr(stdscr, y, x, " " * (len(prompt) + 40)) # Clear line
        safe_addstr(stdscr, y, x, f"{prompt} {query}")
        safe_addstr(stdscr, y, x + len(prompt) + 1 + len(query), "_", curses.A_BLINK)
        stdscr.refresh()
        
        k = stdscr.getch()
        if k == -1: time.sleep(0.02); continue
        
        # Check for Alt+Left (Back) - commonly 542 or ESC + KEY_LEFT
        if k == 542 or k == 543: return (query, "BACK") # 543 is Alt+Right, 542 is Alt+Left
        
        if k == 27: # Potential Alt sequence or ESC
            stdscr.nodelay(True)
            k2 = stdscr.getch()
            if k2 == curses.KEY_LEFT: return (query, "BACK")
            if k2 == curses.KEY_RIGHT: return (query, "NEXT")
            if k2 == -1: return (None, "CANCEL") # True ESC
        
        if k in [10, 13]: return (query, "NEXT")
        elif k in [127, 8, curses.KEY_BACKSPACE]: query = query[:-1]
        elif 32 <= k <= 126: query += chr(k)
    stdscr.nodelay(False)

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
                    p, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "SELECT PROJECT", projs)
                    if not p: break

                    if p == "+ ADD NEW PROJECT":
                        new_p = text_input(stdscr, h//2, w//2 - 20, "PROJECT NAME:")
                        if new_p: add_project(new_p); cfg = load_config()
                    elif p:
                        act, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, f"MANAGE {p}", ["Edit Tags", "Edit Color", "Delete Project", "Cancel"])
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
                c, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "SELECT CLASS", cls_names)
                if c == "+ ADD NEW CLASS":
                    name = text_input(stdscr, h//2, w//2 - 20, "NEW CLASS NAME:")
                    if name:
                        tags = text_input(stdscr, h//2 + 4, w//2 - 20, "KEYWORDS (comma sep):")
                        if tags:
                            cfg['classes'].append({"name": name, "tags": [t.strip() for t in tags.split(',') if t.strip()]})
                elif c:
                    cls = next((x for x in cfg['classes'] if x['name'] == c), None)
                    if cls:
                        act, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, f"MANAGE {c}", ["Edit Name", "Edit Tags", "Delete Class", "Cancel"])
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
                    # Use standard high-contrast selection (Black/White) to ensure readability
                    attr = curses.color_pair(0) | curses.A_REVERSE
                else:
                    attr = curses.color_pair(p_color_id) if p_color_id else 0
                
                # Row content
                row_str = f"{tm_str:<6} | {p_name[:12]:<12} | {it.get('task','-')[:25]:<25} | {dm:<5} | {st[:10]:<10} | {'1.0x' if st.endswith('SUCCESS') else '-'}"
                safe_addstr(stdscr, 4+i, 2, row_str, attr)
        
        # Footer Help
        nav_help = "[TAB] View  [[] Day -  []] Day +  [Space] Dtls  [N] New  [L] Todo  [D] Del"
        safe_addstr(stdscr, h-1, 2, f"{nav_help}  [H] Heat  [W] Week  [R] Raid  [P] Pref  [Q] Quit", curses.color_pair(4))
        
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
        if k in [ord('q'), ord('Q')]: return 'QUIT'
        elif k == curses.KEY_UP: idx -= 1
        elif k == curses.KEY_DOWN: idx += 1
        elif k == ord(' ') and display_history:
             if 0 <= idx < len(display_history):
                 # Adapt history item to task data structure
                 item = display_history[idx]
                 # Try to find the original task content in todos to get tags/desc if possible?
                 # But history items are snapshots. We'll use what we have.
                 
                 # Create a mock tree node compatible with show_neobrutalist_popup
                 mock_data = {
                     'id': item.get('id', 'history'),
                     'project': item.get('project', 'General'),
                     'content': item.get('task', 'No Task'),
                     'date': datetime.fromisoformat(item['timestamp']).strftime("%Y-%m-%d"),
                     'status': 'DONE' if item.get('status')=='completed' else 'TERM',
                     'tags': [], # History doesn't store tags by default currently, unless we change save_session
                     'description': f"Logged on: {datetime.fromisoformat(item['timestamp']).strftime('%Y-%m-%d %H:%M')}\nDuration: {item.get('duration_minutes',0)} minutes"
                 }
                 
                 mock_tree = [{'type': 'item', 'data': mock_data}]
                 show_neobrutalist_popup(stdscr, mock_tree, 0)

def show_timer_view(stdscr):
    btn = 0
    focus_idx = 0
    active_section = 'CONTROLS' # 'CONTROLS' or 'FOCUS'
    
    while True:
        def render():
            tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx()
            
            # Draw Focus List
            focus_list = TODO_STATE.get('focus_queue', [])
            todos = load_todos()
            f_items_local = [t for t in todos if t.get('focused', False)]
            
            split_x = w // 2
            
            # --- LEFT SIDE: CURRENT TIMER ---
            if SESSION['active']:
                cfg = load_config()
                p_color_id = cfg.get('project_colors', {}).get(SESSION['project'], 0)
                p_attr = curses.color_pair(p_color_id) if p_color_id else 0
                
                draw_box(stdscr, 1, 2, 6, split_x - 4, "DETAILS")
                safe_addstr(stdscr, 2, 4, f"PROJECT: {SESSION['project']}", p_attr|curses.A_BOLD)
                safe_addstr(stdscr, 3, 4, f"TASK:    {SESSION['task']}")
                
                elapsed = SESSION['elapsed_before_pause'] + (time.time()-SESSION['start_time'] if SESSION['state']=='running' else 0)
                rem = max(0, SESSION['duration_secs'] - elapsed); t_str = format_duration(rem)
                color = curses.color_pair(4) if SESSION['state']=='running' else curses.color_pair(6)
                if SESSION['state']=='finished': color = curses.color_pair(2)
                
                draw_big_text(stdscr, h//2 - 4, (split_x - 30)//2, t_str if SESSION['show_colon'] else t_str.replace(":"," "), color)
                
                # Progress Bar
                bar_y = h//2 + 5; bar_w = split_x - 10
                if bar_w > 0:
                    draw_box(stdscr, bar_y - 1, 2, 3, bar_w + 4)
                    pct = 1.0 - (rem / SESSION['duration_secs']) if SESSION['duration_secs'] > 0 else 1.0
                    if SESSION['state'] == 'finished': pct = 1.0
                    fld = int(bar_w * pct)
                    safe_addstr(stdscr, bar_y, 4, "█"*fld + "░"*(bar_w-fld), curses.color_pair(3))
                
                safe_addstr(stdscr, bar_y+3, 4, f"STATUS: {SESSION['state'].upper()}", color|curses.A_BOLD)

                # Controls
                btns = ["MENU", "RESTART", "QUIT"] if SESSION['state']=='finished' else ["PAUSE" if SESSION['state']=='running' else "RESUME", "STOP", "RESTART", "BACK", "QUIT"]
                t_w = sum(len(b)+4 for b in btns) + (len(btns)-1)*2; x = (split_x - t_w)//2
                for i, lbl in enumerate(btns):
                    attr = curses.color_pair(1)
                    if active_section == 'CONTROLS' and i == btn: attr |= curses.A_REVERSE
                    safe_addstr(stdscr, h-10, x, f"[ {lbl} ]", attr); x += len(lbl)+6
            else:
                 safe_addstr(stdscr, 5, 5, "NO ACTIVE TIMER", curses.A_DIM)
                 safe_addstr(stdscr, 7, 5, "Select a task from the list to start.", curses.A_BOLD)

            # --- RIGHT SIDE: FOCUS LIST ---
            draw_box(stdscr, 1, split_x, h-8, w - split_x - 1, "QUICK START LIST")
            if not f_items_local:
                safe_addstr(stdscr, 3, split_x + 2, "No focused tasks.", curses.A_DIM)
                safe_addstr(stdscr, 4, split_x + 2, "Press 'f' in Todo List to add.", curses.A_DIM)
            else:
                list_h = h - 12
                # Scroll logic if needed? For now simple list
                for i, item in enumerate(f_items_local[:list_h]):
                    attr = 0
                    if active_section == 'FOCUS' and i == focus_idx: attr |= curses.A_REVERSE
                    safe_addstr(stdscr, 3+i, split_x + 2, f"• {item['content'][:30]}", attr)
            
            draw_pip_timer(stdscr)
            return f_items_local, btns if SESSION['active'] else []

        f_items, btns = render()
        
        stdscr.refresh(); stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k == -1: time.sleep(0.05); continue
        
        nav = check_nav_keys(k); 
        if nav and nav != 'TIMER': return nav
        
        if k == 9: # TAB
            active_section = 'FOCUS' if active_section == 'CONTROLS' else 'CONTROLS'
        
        elif active_section == 'CONTROLS' and SESSION['active']:
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
        
        elif active_section == 'FOCUS':
            if k == curses.KEY_UP: focus_idx = max(0, focus_idx - 1)
            elif k == curses.KEY_DOWN: focus_idx = min(len(f_items)-1, focus_idx + 1)
            elif k == ord(' ') and f_items:
                item = f_items[focus_idx]
                cfg = load_config()
                while True:
                    render()
                    draw_neobrutalist_card(stdscr, item, cfg.get('project_colors', {}))
                    stdscr.refresh()
                    k2 = stdscr.getch()
                    if k2 in [ord(' '), 27]: break
                    time.sleep(0.05)
            elif k in [10, 13] and f_items:
                target = f_items[focus_idx]
                if SESSION['active']: terminate_session()
                d = select_duration(stdscr)
                if d:
                    start_new_session(target.get('project', 'General'), target['content'], d)
                    active_section = 'CONTROLS' 

        if k == 27: return 'HISTORY'

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
        keys = [("[N]","New"), ("[L]","Todo"), ("[T]","Timer"), ("[H]","Heatmap"), ("[W]","Dungeon"), ("[R]","Raid"), ("[D]","Delete"), ("[P]","Prefs")]
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

def setup_colors():
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

def fuzzy_select(stdscr, y, x, title, options, p_colors=None, header_list=None):
    if not options: return (None, "NEXT")
    query = ""
    sel_idx = 0
    box_h = 12 if not header_list else 14
    stdscr.nodelay(True)
    while True:
        matches = [o for o in options if not query or query.lower() in o.lower()]
        if sel_idx >= len(matches): sel_idx = max(0, len(matches)-1)
        
        # Clear area
        for i in range(box_h): safe_addstr(stdscr, y+i, x, " " * 45)
        
        draw_box(stdscr, y, x, box_h, 45, title)
        
        y_off = 2
        if header_list:
            h_str = ", ".join(header_list)
            if len(h_str) > 38: h_str = "..." + h_str[-35:]
            safe_addstr(stdscr, y+y_off, x+2, f"PICKED: {h_str}", curses.color_pair(2)|curses.A_BOLD)
            y_off += 2
            
        safe_addstr(stdscr, y+y_off, x+2, "SEARCH: " + query)
        safe_addstr(stdscr, y+y_off, x+10+len(query), "_", curses.A_BLINK)
        
        for i, m in enumerate(matches[:7]):
            attr = curses.A_REVERSE if i == sel_idx else 0
            if p_colors and m in p_colors:
                 attr |= curses.color_pair(p_colors[m])
            safe_addstr(stdscr, y+y_off+2+i, x+4, f" {m} ", attr)
            
        stdscr.refresh()
        k = stdscr.getch()
        if k == -1: time.sleep(0.02); continue
        
        if k == 542: return (None, "BACK") # Alt+Left
        if k == 543: return (None, "NEXT") # Alt+Right
        if k == 27:
            k2 = stdscr.getch()
            if k2 == curses.KEY_LEFT: return (None, "BACK")
            if k2 == curses.KEY_RIGHT: return (None, "NEXT")
            if k2 == -1: return (None, "CANCEL")
            
        if k in [10, 13]: return (matches[sel_idx] if matches else None, "NEXT")
        elif k == curses.KEY_UP: sel_idx = max(0, sel_idx - 1)
        elif k == curses.KEY_DOWN: sel_idx = min(len(matches)-1, sel_idx + 1)
        elif k in [127, 8, curses.KEY_BACKSPACE]: query = query[:-1]; sel_idx = 0
        elif 32 <= k <= 126: query += chr(k); sel_idx = 0
    stdscr.nodelay(False)

def select_date_dialog(stdscr, y, x):
    today = datetime.now()
    options = []
    for i in range(6):
        target = today + timedelta(days=i)
        label = "Today" if i == 0 else ("Tomorrow" if i == 1 else f"In {i} days")
        date_str = target.strftime("%Y-%m-%d")
        display = f"{label:<12} ({target.strftime('%a %d %b')})"
        options.append((display, date_str))
    
    options.append(("Custom...", "CUSTOM"))
    
    choice, action = fuzzy_select(stdscr, y, x, "SELECT DATE", [o[0] for o in options])
    if action != "NEXT": return (None, action)
    if choice is None: return (None, "CANCEL")
    
    for display, date_str in options:
        if display == choice:
            if date_str == "CUSTOM":
                res, a = text_input(stdscr, y, x, "ENTER DATE (YYYY-MM-DD):", today.strftime("%Y-%m-%d"))
                return (res, a)
            return (date_str, "NEXT")
    return (None, "CANCEL")

def card_text_input(stdscr, y, x, prompt, attr, prefill=""):
    query = prefill
    stdscr.nodelay(True)
    while True:
        # Render prompt + current query
        safe_addstr(stdscr, y, x, " " * (len(prompt) + 40))
        safe_addstr(stdscr, y, x, f"{prompt} {query}", attr)
        safe_addstr(stdscr, y, x + len(prompt) + 1 + len(query), "_", attr | curses.A_BLINK)
        stdscr.refresh()
        
        k = stdscr.getch()
        if k == -1: time.sleep(0.02); continue
        
        if k == 542: return (query, "BACK")
        if k == 543: return (query, "NEXT")
        if k == 27:
            k2 = stdscr.getch()
            if k2 == curses.KEY_LEFT: return (query, "BACK")
            if k2 == curses.KEY_RIGHT: return (query, "NEXT")
            if k2 == -1: return (None, "CANCEL")
            
        if k in [10, 13]: return (query, "NEXT")
        elif k in [127, 8, curses.KEY_BACKSPACE]: query = query[:-1]
        elif 32 <= k <= 126: query += chr(k)
    stdscr.nodelay(False)

def multi_select_tags(stdscr, y, x, title, existing_tags, selected=None):
    if selected is None: selected = []
    while True:
        options = ["[ DONE ]", "[ + ADD MANUAL ]"] + [t for t in existing_tags if t not in selected]
        res, action = fuzzy_select(stdscr, y, x, title, options, header_list=selected)
        
        if action != "NEXT": return (selected, action)
        if res is None or res == "[ DONE ]": return (selected, "NEXT")
        if res == "[ + ADD MANUAL ]":
            manual, m_action = card_text_input(stdscr, y + 14, x, "NEW TAG:", curses.A_REVERSE)
            if m_action == "BACK": return (selected, "BACK")
            if manual:
                new_tags = [t.strip().upper() for t in manual.split(',') if t.strip()]
                selected.extend(new_tags)
        else:
            selected.append(res)

def add_new_todo_dialog(stdscr):
    h, w = stdscr.getmaxyx()
    card_w, card_h = min(84, int(w * 0.9)), min(26, int(h * 0.9))
    cy, cx = (h - card_h) // 2, (w - card_w) // 2
    
    cfg = load_config()
    p_colors = cfg.get('project_colors', {})
    all_projs = get_unique_projects() + ["+ NEW PROJECT"]
    
    state = {
        'project': None, 'content': "", 'description': "", 
        'tags': [], 'date': None, 'color_id': 4
    }
    
    steps = ['PROJECT', 'NAME', 'DESCRIPTION', 'TAGS', 'DATE', 'CONFIRM']
    cur_step = 0

    def draw_base_card(color_id, title):
        stdscr.erase(); draw_pip_timer(stdscr)
        for y in range(cy + 1, cy + card_h + 1): safe_addstr(stdscr, y, cx + 2, " " * card_w, curses.color_pair(8))
        attr = curses.color_pair(color_id) | curses.A_REVERSE | curses.A_BOLD
        for y in range(cy, cy + card_h): safe_addstr(stdscr, y, cx, " " * card_w, attr)
        safe_addstr(stdscr, cy+1, cx+2, f"  {title}  ", curses.color_pair(0)|curses.A_BOLD)
        return attr

    while 0 <= cur_step < len(steps):
        step = steps[cur_step]
        
        if step == 'PROJECT':
            sel_idx = 0
            if state['project'] in all_projs: sel_idx = all_projs.index(state['project'])
            while True:
                p_name = all_projs[sel_idx]; c_id = p_colors.get(p_name, 4)
                if p_name == "+ NEW PROJECT": c_id = 0
                main_attr = draw_base_card(c_id, "STEP 1: SELECT PROJECT")
                for i, p in enumerate(all_projs[:15]):
                    p_attr = curses.A_REVERSE if i == sel_idx else 0
                    p_col = p_colors.get(p, 0)
                    if i != sel_idx and p_col:
                        try: p_attr |= curses.color_pair(p_col)
                        except: pass
                    safe_addstr(stdscr, cy+4+i, cx+4, f" {p} ", p_attr)
                stdscr.refresh()
                k = stdscr.getch()
                if k == 27: return None # Exit dialog
                elif k == 542: return None # Back from first step
                elif k == curses.KEY_UP: sel_idx = max(0, sel_idx - 1)
                elif k == curses.KEY_DOWN: sel_idx = min(len(all_projs)-1, sel_idx + 1)
                elif k in [10, 13]:
                    if all_projs[sel_idx] == "+ NEW PROJECT":
                        res, a = text_input(stdscr, cy+4, cx+4, "NEW PROJECT NAME:")
                        if a == "CANCEL": return None
                        if res:
                            state['project'] = res
                            state['color_id'] = select_color(stdscr, cy+6, cx+4) or 4
                            add_project(state['project'], state['color_id'], [])
                    else:
                        state['project'] = all_projs[sel_idx]
                        state['color_id'] = c_id
                    cur_step += 1; break

        elif step == 'NAME':
            main_attr = draw_base_card(state['color_id'], f"PROJECT: {state['project'].upper()}")
            res, action = card_text_input(stdscr, cy+5, cx+4, "TASK NAME:", main_attr, prefill=state['content'])
            if action == "CANCEL": return None
            state['content'] = res or ""
            cur_step += (1 if action == "NEXT" else -1)

        elif step == 'DESCRIPTION':
            main_attr = draw_base_card(state['color_id'], f"PROJECT: {state['project'].upper()}")
            safe_addstr(stdscr, cy+5, cx+4, f"NAME: {state['content']}", main_attr)
            res, action = card_text_input(stdscr, cy+7, cx+4, "DESCRIPTION:", main_attr, prefill=state['description'])
            if action == "CANCEL": return None
            state['description'] = res or ""
            cur_step += (1 if action == "NEXT" else -1)

        elif step == 'TAGS':
            main_attr = draw_base_card(state['color_id'], f"PROJECT: {state['project'].upper()}")
            safe_addstr(stdscr, cy+5, cx+4, f"NAME: {state['content']}", main_attr)
            safe_addstr(stdscr, cy+7, cx+4, f"DESC: {state['description'][:40]}...", main_attr)
            proj_tags = get_project_tags(state['project'])
            res, action = multi_select_tags(stdscr, cy+9, cx+4, "SELECT TAGS", proj_tags, selected=state['tags'])
            if action == "CANCEL": return None
            state['tags'] = res
            cur_step += (1 if action == "NEXT" else -1)

        elif step == 'DATE':
            main_attr = draw_base_card(state['color_id'], f"PROJECT: {state['project'].upper()}")
            safe_addstr(stdscr, cy+5, cx+4, f"NAME: {state['content']}", main_attr)
            safe_addstr(stdscr, cy+7, cx+4, f"DESC: {state['description'][:40]}...", main_attr)
            safe_addstr(stdscr, cy+9, cx+4, f"TAGS: {' '.join(['#'+t for t in state['tags']])}", main_attr)
            res, action = select_date_dialog(stdscr, cy+11, cx+4)
            if action == "CANCEL": return None
            state['date'] = res
            cur_step += (1 if action == "NEXT" else -1)

        elif step == 'CONFIRM':
            main_attr = draw_base_card(state['color_id'], "CONFIRM TASK")
            safe_addstr(stdscr, cy+4, cx+4, f"PROJECT: {state['project']}", main_attr)
            safe_addstr(stdscr, cy+6, cx+4, f"NAME:    {state['content']}", main_attr)
            safe_addstr(stdscr, cy+8, cx+4, f"DATE:    {state['date']}", main_attr)
            safe_addstr(stdscr, cy+10, cx+4, f"TAGS:    {' '.join(['#'+t for t in state['tags']])}", main_attr)
            msg = " [ENTER] TO SAVE  [ALT+LEFT] TO GO BACK  [ESC] DISCARD "
            safe_addstr(stdscr, cy+card_h-3, cx+(card_w-len(msg))//2, msg, curses.color_pair(0)|curses.A_BOLD)
            stdscr.refresh()
            while True:
                k = stdscr.getch()
                if k in [10, 13]:
                    add_todo(state['content'], state['date'], state['project'], state['tags'], state['description'])
                    return state['project']
                elif k == 27: return None
                elif k == 542: cur_step -= 1; break
    return None



def update_todo(todo_id, content, date_str, project, tags, description):
    todos = load_todos()
    for t in todos:
        if t['id'] == todo_id:
            t['content'] = content
            t['date'] = date_str
            t['project'] = project
            t['tags'] = clean_tags(tags)
            t['description'] = description
            break
    save_todos(todos)

def edit_todo_dialog(stdscr, item):
    h, w = stdscr.getmaxyx()
    # Pre-fill
    orig_content = item['content']
    orig_desc = item.get('description', '')
    orig_date = item.get('date', '')
    orig_proj = item.get('project', 'General')
    orig_tags = ",".join(item.get('tags', []))
    
    # 1. Content
    content = text_input(stdscr, h//2 - 6, w//2 - 20, "EDIT TASK CONTENT:", orig_content)
    if content is None: return False
    if not content.strip(): return False
    
    # 2. Description
    desc = text_input(stdscr, h//2 - 4, w//2 - 20, "EDIT DESCRIPTION:", orig_desc)
    if desc is None: desc = ""
    
    # 3. Date
    d_str = text_input(stdscr, h//2 - 2, w//2 - 20, "EDIT DATE:", orig_date)
    if d_str is None: return False
    
    # 4. Project
    # We can't easily pre-select in fuzzy_select, so we let user choose again or keep current
    projs = ["KEEP CURRENT (" + orig_proj + ")"] + ["General"] + get_unique_projects() + ["+ NEW PROJECT"]
    p, _ = fuzzy_select(stdscr, h//2 + 2, w//2 - 20, "EDIT PROJECT", projs)
    if p is None: return False
    
    final_proj = orig_proj
    new_proj_color = None
    new_proj_tags = []
    
    if p.startswith("KEEP CURRENT"):
        final_proj = orig_proj
    elif p == "+ NEW PROJECT":
        final_proj = text_input(stdscr, h//2 + 2, w//2 - 20, "NEW PROJECT NAME:")
        if not final_proj: return False
        
        # New Project Setup
        p_tags_str = text_input(stdscr, h//2 + 4, w//2 - 20, "PROJECT TAGS (comma sep):")
        new_proj_tags = [t.strip() for t in p_tags_str.split(',')] if p_tags_str else []
        curses.flushinp()
        new_proj_color = select_color(stdscr, h//2 - 5, w//2 + 22)
    else:
        final_proj = p

    # 5. Tags
    tags_str = text_input(stdscr, h//2 + 6, w//2 - 20, "EDIT TAGS (comma sep):", orig_tags)
    if tags_str is None: return False
    tags = [t.strip() for t in tags_str.split(',')] if tags_str else []
    
    # Save
    msg = " SAVE CHANGES? (y/n/Enter) "
    safe_addstr(stdscr, h-1, 2, " " * (w-3))
    safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.timeout(-1)
    k = stdscr.getch()
    stdscr.timeout(50)
    
    if k in [ord('y'), ord('Y'), 10, 13]:
        # Handle new project creation if needed
        if p == "+ NEW PROJECT":
             add_project(final_proj, new_proj_color, new_proj_tags)
        
        update_todo(item['id'], content, d_str, final_proj, tags, desc)
        return True
    
    return False

def get_all_used_tags():
    todos = load_todos()
    tags = set()
    for t in todos:
        for tag in t.get('tags', []):
            tags.add(tag)
    return sorted(list(tags))

def tag_filtering_dialog(stdscr):
    h, w = stdscr.getmaxyx()
    all_tags = get_all_used_tags()
    selected_tags = []
    query = ""
    matches = []
    sel_idx = 0
    
    # Box Config
    box_w = min(60, w - 4)
    box_h = 16
    box_y = (h - box_h) // 2
    box_x = (w - box_w) // 2
    
    # Helper to clear box area
    def clear_box_area():
        for y in range(box_h):
            safe_addstr(stdscr, box_y+y, box_x, " " * box_w)
    
    # PHASE 1: TAG SELECTION
    while True:
        # Draw Over (Fake Clear of Box Area)
        clear_box_area()
        draw_box(stdscr, box_y, box_x, box_h, box_w, "FILTER BY TAGS")
        
        # 1. Show Selected
        sel_str = ", ".join(selected_tags)
        if len(sel_str) > box_w - 6: sel_str = "..." + sel_str[-(box_w-9):]
        safe_addstr(stdscr, box_y+2, box_x+2, f"SELECTED: [{sel_str}]", curses.color_pair(2)|curses.A_BOLD)
        
        # 2. Input
        safe_addstr(stdscr, box_y+4, box_x+2, "ADD TAG: " + query)
        safe_addstr(stdscr, box_y+4, box_x+11+len(query), "_", curses.A_BLINK)
        
        # 3. Matches
        matches = [t for t in all_tags if t not in selected_tags and (not query or query.lower() in t.lower())]
        
        display_list = matches[:8]
        if not query and not matches and selected_tags:
             display_list = ["[ CONFIRM FILTER ]"]
        elif query == "" and matches:
             display_list = ["[ CONFIRM FILTER ]"] + matches[:7]
        
        if sel_idx >= len(display_list): sel_idx = max(0, len(display_list)-1)
        
        for i, item in enumerate(display_list):
            attr = curses.A_REVERSE if i == sel_idx else 0
            safe_addstr(stdscr, box_y+6+i, box_x+4, f" {item} ", attr)
            
        safe_addstr(stdscr, box_y+box_h-2, box_x+2, "[Enter] Add/Confirm  [UP/DOWN] Select  [ESC] Cancel", curses.A_DIM)
        
        stdscr.refresh()
        stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        
        if k == -1: time.sleep(0.05); continue
        
        if k == 27: return None # Cancel
        elif k == curses.KEY_UP: sel_idx = max(0, sel_idx - 1)
        elif k == curses.KEY_DOWN: sel_idx = min(len(display_list) - 1, sel_idx + 1)
        elif k in [curses.KEY_BACKSPACE, 127, 8]: 
            query = query[:-1]
            sel_idx = 0
        elif k in [10, 13]: # Enter
            if display_list:
                choice = display_list[sel_idx]
                if choice == "[ CONFIRM FILTER ]":
                    break # Go to options
                else:
                    selected_tags.append(choice)
                    query = ""
                    sel_idx = 0
            elif query: 
                # Allow custom
                pass
        elif 32 <= k <= 126 and len(query) < 20:
            query += chr(k)
            sel_idx = 0 
            
    # Phase 2: Options (Inside same box)
    status_mode = 'ALL' # ALL, PENDING, DONE
    inc_tagless = False
    
    # Prompt 1: Status Filter
    clear_box_area()
    draw_box(stdscr, box_y, box_x, box_h, box_w, "FILTER OPTIONS (1/2)")
    msg1 = "FILTER BY STATUS:"
    safe_addstr(stdscr, box_y+6, box_x + (box_w-len(msg1))//2, msg1, curses.A_BOLD)
    
    opts = "[A] ALL  [P] PENDING ONLY  [D] DONE ONLY"
    safe_addstr(stdscr, box_y+8, box_x + (box_w-len(opts))//2, opts, curses.color_pair(3))
    
    stdscr.refresh()
    while True:
        k = stdscr.getch()
        if k in [ord('a'), ord('A'), 13, 10]: status_mode = 'ALL'; break
        elif k in [ord('p'), ord('P')]: status_mode = 'PENDING'; break
        elif k in [ord('d'), ord('D')]: status_mode = 'DONE'; break
        elif k == 27: return None
        
    # Prompt 2: Tagless
    clear_box_area()
    draw_box(stdscr, box_y, box_x, box_h, box_w, "FILTER OPTIONS (2/2)")
    msg2 = "INCLUDE ITEMS WITH NO TAGS?"
    safe_addstr(stdscr, box_y+6, box_x + (box_w-len(msg2))//2, msg2, curses.A_BOLD)
    safe_addstr(stdscr, box_y+8, box_x + (box_w-14)//2, "[Y] YES  [N] NO", curses.color_pair(3))
    stdscr.refresh()
    while True:
        k = stdscr.getch()
        if k in [ord('y'), ord('Y')]: inc_tagless = True; break
        elif k in [ord('n'), ord('N'), 13, 10]: break
        elif k == 27: return None
        
    return (selected_tags, status_mode, inc_tagless)

def draw_todo_tree(stdscr, tree, sel_idx, scroll_idx, today_str, p_colors, delete_pending_idx):
    h, w = stdscr.getmaxyx()
    # Reserve space for PIP timer at bottom if active
    # PIP is at h-6, height 5. So occupy h-6 to h-1.
    # Tree starts at 4.
    bottom_margin = 5
    if SESSION['active']: bottom_margin = 11
    
    list_h = max(1, h - bottom_margin)
    
    if not tree: 
        safe_addstr(stdscr, 4, 4, "No tasks found.", curses.A_DIM)
        return
    
    # Selection/Scroll clamping
    sel_idx = max(0, min(sel_idx, len(tree)-1))
    if sel_idx < scroll_idx: scroll_idx = sel_idx
    elif sel_idx >= scroll_idx + list_h: scroll_idx = sel_idx - list_h + 1
    
    for i in range(list_h):
        ii = scroll_idx + i
        if ii >= len(tree): break
        node = tree[ii]
        is_sel = (ii == sel_idx)
        attr = curses.A_REVERSE if is_sel else 0
        
        # Margin Asterisk
        show_ast = False
        ast_col = 5
        if node['type'] == 'item':
            if node['data']['status'] == 'pending': 
                show_ast = True; ast_col = p_colors.get(node['data'].get('project', 'General'), 5)
        elif node['type'] in ['project', 'date_group', 'group']:
            if node['done'] < node['total']: 
                show_ast = True; ast_col = p_colors.get(node.get('key', node.get('parent', 'General')), 5)
        
        if show_ast:
            try: col_p = curses.color_pair(ast_col)
            except: col_p = curses.color_pair(5)
            safe_addstr(stdscr, 4+i, 0, "\U0001F7BA", col_p)

        # Rendering
        if node['type'] == 'group':
            k = node['key']
            lbl = f"  {k}"
            try:
                dt = datetime.strptime(k, "%Y-%m-%d")
                lbl = dt.strftime("%a %d/%b/%Y").upper()
                lbl = f"★ {lbl}" if k == today_str else f"  {lbl}"
            except: pass
            pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
            icon = "[-]" if k in TODO_STATE['expanded_daily'] else "[+]"
            is_past_pending = k < today_str and node['done'] < node['total']
            h_attr = curses.color_pair(5)|curses.A_BOLD if is_past_pending else curses.color_pair(4)
            safe_addstr(stdscr, 4+i, 2, f"{icon} {lbl:<25} {pct:>3}%", attr|h_attr)
        
        elif node['type'] == 'project':
            k = node['key']
            pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
            is_open = k in TODO_STATE['expanded_project']
            icon = "[-]" if is_open else "[+]"
            col = curses.color_pair(p_colors.get(k, 3))
            safe_addstr(stdscr, 4+i, 2, f"{icon} {k:<25} {pct:>3}%", attr|col|curses.A_BOLD)
            
        elif node['type'] == 'date_group':
            d, p_name = node['date'], node['parent']
            lbl = d
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                lbl = dt.strftime("%a %d/%b/%Y").upper()
                lbl = f"★ {lbl}" if d == today_str else f"  {lbl}"
            except: pass
            pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
            col = curses.color_pair(p_colors.get(p_name, 3))
            is_backlog = d < today_str and node['done'] < node['total']
            line = ("  ├─" if not node['is_last'] else "  └─") if not is_backlog else ("  ├╌" if not node['is_last'] else "  └╌")
            d_attr = curses.color_pair(5)|curses.A_BOLD if is_backlog else curses.color_pair(4)
            safe_addstr(stdscr, 4+i, 2, line, col)
            safe_addstr(stdscr, 4+i, 6, f"{lbl:<23} {pct:>3}%", attr|d_attr)

        elif node['type'] == 'item':
            item = node['data']
            st = "[x]" if item['status']=='done' else "[ ]"
            is_overdue = (item.get('date', '9999-99-99') < today_str) and (item['status'] == 'pending')
            col = curses.color_pair(2) if item['status'] == 'done' else (curses.color_pair(5) if is_overdue else 0)
            
            # Focus Highlighting
            if item.get('focused', False):
                 p_name = item.get('project', 'General')
                 p_col_id = p_colors.get(p_name, 0)
                 # Invert the project color or use REVERSE
                 col = curses.color_pair(p_col_id) | curses.A_REVERSE if p_col_id else curses.A_REVERSE

            t_str = " " + " ".join([f"#{t}" for t in item.get('tags', []) if t])
            
            if TODO_STATE['mode'] == 'DAILY':
                p_name = item.get('project', 'General')
                if p_name != "General" and not is_overdue and item['status'] != 'done' and item['id'] not in TODO_STATE.get('focus_queue', []):
                    try: col = curses.color_pair(p_colors.get(p_name, 0))
                    except: pass
                safe_addstr(stdscr, 4+i, 4, f"{('╌╌ ' if is_overdue else '   ')}{st} {p_name}: {item['content']}{t_str}", attr|col)
            else:
                p_name = node.get('parent', '').split('|')[0]
                t_col = curses.color_pair(p_colors.get(p_name, 3))
                line = f"  {'│' if not node.get('parent_last') else ' '}  {'├' if not node.get('is_last') else '└'}{'╌' if item['status'] == 'pending' else '─'}"
                safe_addstr(stdscr, 4+i, 2, line, t_col)
                safe_addstr(stdscr, 4+i, 9, f"{st} {item['content']}{t_str}", attr|col)
            
        if ii == delete_pending_idx:
            safe_addstr(stdscr, 4+i, w-25, " PRESS 'D' AGAIN TO DELETE ", curses.color_pair(5)|curses.A_BOLD|curses.A_REVERSE)
    return scroll_idx

def draw_neobrutalist_card(stdscr, item, p_colors):
    h, w = stdscr.getmaxyx()
    card_w, card_h = min(84, int(w * 0.9)), min(26, int(h * 0.9))
    cy, cx = (h - card_h) // 2, (w - card_w) // 2
    
    p_name = item.get('project', 'General')
    p_col_id = p_colors.get(p_name, 4)
    
    # Shadow & Body
    for y in range(cy + 1, cy + card_h + 1): safe_addstr(stdscr, y, cx + 2, " " * card_w, curses.color_pair(8))
    main_attr = curses.color_pair(p_col_id) | curses.A_REVERSE | curses.A_BOLD
    for y in range(cy, cy + card_h): safe_addstr(stdscr, y, cx, " " * card_w, main_attr)
        
    # Stickers
    st_attr = curses.color_pair(0) | curses.A_BOLD
    safe_addstr(stdscr, cy+1, cx+2, f"  {p_name.upper()}  ", st_attr)
    safe_addstr(stdscr, cy+2, cx+4, f" {item.get('date', 'NA')} ", st_attr)
    status = item.get('status', 'PENDING').upper()
    s_col = curses.color_pair(2 if status == 'DONE' or status == 'COMPLETED' else 5)
    safe_addstr(stdscr, cy+1, cx+card_w-len(status)-6, f" {status} ", s_col | curses.A_BOLD | curses.A_REVERSE)
    
    # Content
    content, inner_w = item.get('content', ''), card_w - 8
    lines = []
    # Split by newline first
    raw_lines = content.split('\n')
    for r_line in raw_lines:
        while len(r_line) > inner_w:
            split = r_line[:inner_w].rfind(' ')
            if split == -1: split = inner_w
            lines.append(r_line[:split])
            r_line = r_line[split:].strip()
        lines.append(r_line)

    for i, line in enumerate(lines[:5]): safe_addstr(stdscr, cy+5+i, cx+4, line, main_attr)
    
    desc = item.get('description', '')
    if desc:
        safe_addstr(stdscr, cy+11, cx+2, "▀" * (card_w-4), main_attr)
        safe_addstr(stdscr, cy+12, cx+4, "DESCRIPTION:", main_attr|curses.A_UNDERLINE)
        d_lines = []
        raw_d_lines = desc.split('\n')
        for r_line in raw_d_lines:
            while len(r_line) > inner_w:
                split = r_line[:inner_w].rfind(' ')
                if split == -1: split = inner_w
                d_lines.append(r_line[:split])
                r_line = r_line[split:].strip()
            d_lines.append(r_line)
            
        for i, line in enumerate(d_lines[:8]): safe_addstr(stdscr, cy+14+i, cx+4, line, main_attr)

def show_neobrutalist_popup(stdscr, tree, start_idx):
    idx = start_idx
    h, w = stdscr.getmaxyx()
    scroll_idx = 0 # Local scroll tracker for background
    
    while True:
        # 1. Update background (Todo Tree)
        # Recalculate scroll_idx to follow idx
        list_h = h - 5
        if idx < scroll_idx: scroll_idx = idx
        elif idx >= scroll_idx + list_h: scroll_idx = idx - list_h + 1
        
        # Redraw background elements
        tick_timer(); stdscr.erase(); draw_pip_timer(stdscr)
        cfg = load_config()
        p_colors = cfg.get('project_colors', {})
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Render Todo List Tabs/Header
        mode = TODO_STATE['mode']
        tabs = f" [{'DAILY' if mode=='DAILY' else '  DAILY  '}] " + f" [{'PROJECT' if mode=='PROJECT' else '  PROJECT  '}] "
        safe_addstr(stdscr, 1, 2, tabs, curses.color_pair(3)|curses.A_BOLD)
        safe_addstr(stdscr, 2, 2, "="*(w-4), curses.color_pair(3))
        
        draw_todo_tree(stdscr, tree, idx, scroll_idx, today_str, p_colors, -1)
        
        # 2. Flicker Transition Effect (Brief inversion of the whole UI)
        # We only flicker when idx changes, but for simplicity let's do a fast draw
        
        # 3. Draw Card Popup
        node = tree[idx]; item = node['data']
        draw_neobrutalist_card(stdscr, item, p_colors)

        stdscr.refresh()
        k = stdscr.getch()
        if k in [ord(' '), 27]: return idx
        elif k == curses.KEY_UP:
            tmp = idx - 1
            while tmp >= 0 and tree[tmp]['type'] != 'item': tmp -= 1
            if tmp >= 0: idx = tmp
        elif k == curses.KEY_DOWN:
            tmp = idx + 1
            while tmp < len(tree) and tree[tmp]['type'] != 'item': tmp += 1
            if tmp < len(tree): idx = tmp
        elif k in [10, 13, 529]:
            # Guard against history items or non-toggleable items
            if item.get('id') == 'history': return idx 
            
            dur = 15
            if k in [10, 529]:
                dur = select_duration(stdscr)
                if dur is None: dur = 0
            if dur > 0:
                toggle_todo(item['id'], dur)
                try:
                    tree[idx]['data'] = next(t for t in load_todos() if t['id'] == item['id'])
                except: pass


def show_todo_list(stdscr):
    # Use global state for persistence
    mode = TODO_STATE['mode']
    backlog_active = TODO_STATE['backlog_active']
    isolation_filter = TODO_STATE['isolation_filter']
    isolation_type = TODO_STATE['isolation_type']
    active_filter = TODO_STATE['active_filter']
    
    sel_idx = 0
    scroll_idx = 0
    delete_pending_idx = -1
    jump_target = None
    
    while True:
        tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        # Dynamic expansion set based on mode
        expanded = TODO_STATE['expanded_daily'] if mode == 'DAILY' else TODO_STATE['expanded_project']
        
        # Update global state sync
        TODO_STATE['mode'] = mode
        TODO_STATE['backlog_active'] = backlog_active
        TODO_STATE['isolation_filter'] = isolation_filter
        TODO_STATE['isolation_type'] = isolation_type
        TODO_STATE['active_filter'] = active_filter

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

        # 2. Apply Tag/Feature Filter
        if active_filter:
            sel_tags, status_mode, inc_tagless = active_filter
            filtered = []
            for t in todos:
                t_tags = t.get('tags', [])
                has_match = any(tag in t_tags for tag in sel_tags)
                is_tagless = not t_tags
                is_pending = t['status'] == 'pending'
                
                # Logic: Content Match AND Status Match
                
                # 1. Content Match
                content_match = False
                if not sel_tags and not inc_tagless: 
                    content_match = True # No tags selected and not focusing on tagless -> Show all content?
                    # Usually if filter active but no tags selected, maybe just filtering by status?
                    # Let's assume if sel_tags is empty, we show everything unless inc_tagless is true (then show only tagless)
                    if inc_tagless: content_match = is_tagless
                    else: content_match = True
                else:
                    if has_match: content_match = True
                    if inc_tagless and is_tagless: content_match = True
                
                # 2. Status Match
                status_match = True
                if status_mode == 'PENDING' and not is_pending: status_match = False
                if status_mode == 'DONE' and is_pending: status_match = False
                
                if content_match and status_match:
                    filtered.append(t)
            todos = filtered

        # 3. Apply Backlog Filter (on top of isolation)
        if backlog_active:
            todos = [t for t in todos if t.get('date', '9999-99-99') <= today_str and t['status'] == 'pending']

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
                if k in expanded or (isolation_filter and isolation_type == 'date') or backlog_active:
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
                
                if p in expanded or is_isolated_proj or backlog_active:
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
                        
                        if d_key in expanded or is_isolated_dg or backlog_active:
                            for i_t, item in enumerate(d_items):
                                is_last_item = (i_t == len(d_items) - 1)
                                tree.append({'type': 'item', 'data': item, 'parent': d_key, 'is_last': is_last_item, 'parent_last': is_last_date})

        # Ensure sel_idx is within bounds
        if not tree: sel_idx = 0
        elif sel_idx >= len(tree): sel_idx = len(tree) - 1
        if sel_idx < 0: sel_idx = 0

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
            indicator_x += len(iso_label) + 14
            
        # Filter Indicator
        if active_filter:
             safe_addstr(stdscr, 1, indicator_x, " [FILTER ACTIVE] ", curses.color_pair(2)|curses.A_BOLD|curses.A_REVERSE)
            
        safe_addstr(stdscr, 2, 2, "="*(w-4), curses.color_pair(3))
        
        scroll_idx = draw_todo_tree(stdscr, tree, sel_idx, scroll_idx, today_str, p_colors, delete_pending_idx)
        
        nav_hint = "[TAB] View  [B] Backlog: " + ("ON " if backlog_active else "OFF")
        safe_addstr(stdscr, h-1, 2, f"{nav_hint}  [f] Focus  [S] Start  [F] Filter  [I] Isolate  [Space] Dtls  [Enter] Toggle  [D] Del  [ESC] Back", curses.color_pair(4))
        stdscr.refresh()
        stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        
        if k == -1: time.sleep(0.05); continue
        
        nav = check_nav_keys(k)
        if nav and nav != 'TODO' and nav != 'INFO': return nav

        if k == ord('f'):
            if tree and 0 <= sel_idx < len(tree):
                node = tree[sel_idx]
                todos_all = load_todos()
                changed = False
                
                if node['type'] == 'item':
                    t_id = node['data']['id']
                    for t in todos_all:
                        if t['id'] == t_id:
                            t['focused'] = not t.get('focused', False)
                            changed = True; break
                elif node['type'] in ['group', 'project', 'date_group']:
                     # Get all IDs currently visible in this branch
                     child_ids = []
                     curr = sel_idx + 1
                     while curr < len(tree):
                         child = tree[curr]
                         if child.get('parent') == node['key'] or child.get('parent') == f"{node.get('key')}|{node.get('date')}" or (node['type']=='project' and child.get('parent', '').startswith(node['key'])):
                             if child['type'] == 'item':
                                 child_ids.append(child['data']['id'])
                         else: break
                         curr += 1
                     
                     if child_ids:
                         for t in todos_all:
                             if t['id'] in child_ids:
                                 t['focused'] = True # Set all to focused if toggling group
                                 changed = True
                
                if changed:
                    save_todos(todos_all)

        if k in [ord('s'), ord('S')]:
             if tree and 0 <= sel_idx < len(tree):
                 node = tree[sel_idx]
                 if node['type'] == 'item':
                     item = node['data']
                     d = select_duration(stdscr)
                     if d:
                         start_new_session(item.get('project', 'General'), item['content'], d)
                         return 'TIMER'

        if k == ord(' '):
            if tree and 0 <= sel_idx < len(tree):
                node = tree[sel_idx]
                if node['type'] == 'item':
                    sel_idx = show_neobrutalist_popup(stdscr, tree, sel_idx)
        
        if k == ord('F'):
            if active_filter:
                # Prompt to clear
                safe_addstr(stdscr, h-2, 2, " " * (w-1))
                msg = " REMOVE FILTER? (y/n) "
                safe_addstr(stdscr, h//2, w//2 - len(msg)//2, msg, curses.color_pair(5)|curses.A_BOLD|curses.A_REVERSE)
                stdscr.refresh()
                while True:
                    ck = stdscr.getch()
                    if ck in [ord('y'), ord('Y')]: active_filter = None; break
                    elif ck in [ord('n'), ord('N'), 27]: break
            else:
                active_filter = tag_filtering_dialog(stdscr)
                sel_idx = 0; scroll_idx = 0; delete_pending_idx = -1
        
        if k in [ord('e'), ord('E')]:
            if tree and 0 <= sel_idx < len(tree):
                node = tree[sel_idx]
                if node['type'] == 'item':
                    # Edit
                    res = edit_todo_dialog(stdscr, node['data'])
                    if res:
                        # Refresh data
                        sel_idx = 0; scroll_idx = 0; delete_pending_idx = -1
        
        if k in [ord('x'), ord('X')]:
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
            # Preserve expansion state, just reset selection
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
            sel_idx = 0; scroll_idx = 0; delete_pending_idx = -1
        elif k in [curses.KEY_DOWN, ord('j')]: 
            sel_idx += 1; delete_pending_idx = -1
        elif k in [curses.KEY_UP, ord('k')]: 
            sel_idx -= 1; delete_pending_idx = -1
        elif k in [10, 13, 529]: # Enter (13) or Ctrl+Enter (10/529)
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
                    item = node['data']
                    if item['status'] == 'pending':
                        # If Ctrl+Enter, prompt for time. Otherwise default 15.
                        duration = 15
                        if k in [10, 529]:
                            duration = select_duration(stdscr)
                            if duration is None: # Cancelled
                                duration = 0
                        
                        if duration > 0:
                            toggle_todo(item['id'], duration)
                    else:
                        # Toggling back to pending (no time needed)
                        toggle_todo(item['id'])
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
    setup_colors()

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
            p, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "PROJECT", get_unique_projects())
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
            
            t, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "TASK", all_tasks)
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
