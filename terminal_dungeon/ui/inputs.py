import curses
import time
from datetime import datetime, timedelta
from .. import storage
from .. import controller
from ..config import PRESETS, PROJECT_COLORS_NAMES
from ..logic import parse_time_str, clean_tags, get_unique_projects, get_project_tags, get_all_used_tags
from .renderer import safe_addstr, draw_box, draw_pip_timer, draw_neobrutalist_card
from ..controller import tick_timer, add_project, add_todo, update_todo

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
        if k == 542: return (query, "BACK")
        if k == 543: return (query, "NEXT")
        if k == 9: return (query, "NEXT") # TAB
        
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

def card_text_input(stdscr, y, x, prompt, attr, prefill="", max_width=None, multiline=False):
    query = prefill
    cursor_idx = len(query)
    if max_width is None:
        _, w = stdscr.getmaxyx()
        max_width = w - x - 2

    stdscr.nodelay(True)
    while True:
        # 1. Layout & Wrapping Logic
        p_prefix = f"{prompt} "
        avail_w = max_width - len(p_prefix) - 1
        if avail_w < 10: avail_w = 10
        
        marker = "\u0000"
        temp_query = query[:cursor_idx] + marker + query[cursor_idx:]
        manual_parts = temp_query.split('\n')
        
        display_lines = []
        cursor_y_off = 0
        cursor_x_off = 0
        
        for part in manual_parts:
            if not part:
                if marker in part:
                    cursor_y_off = len(display_lines)
                    cursor_x_off = 0
                display_lines.append("")
                continue
            
            # Wrap by characters
            for j in range(0, len(part), avail_w):
                chunk = part[j:j+avail_w]
                if marker in chunk:
                    cursor_y_off = len(display_lines)
                    cursor_x_off = chunk.find(marker)
                    chunk = chunk.replace(marker, "")
                display_lines.append(chunk)

        # 2. Rendering
        num_rows = 15 if multiline else 1
        for i in range(num_rows):
            safe_addstr(stdscr, y + i, x, " " * max_width)
            
        for i, line in enumerate(display_lines[:num_rows]):
            prefix = p_prefix if i == 0 else " " * len(p_prefix)
            safe_addstr(stdscr, y + i, x, prefix, attr)
            safe_addstr(stdscr, y + i, x + len(prefix), line, attr)

        # Cursor
        if cursor_y_off < num_rows:
            safe_addstr(stdscr, y + cursor_y_off, x + len(p_prefix) + cursor_x_off, "_", attr | curses.A_BLINK)
        
        stdscr.refresh()
        
        k = stdscr.getch()
        if k == -1: time.sleep(0.02); continue
        
        # Navigation (Universal)
        if k in [9, 13, curses.KEY_ENTER]: return (query, "NEXT") # Tab or Enter
        if k == 353: return (query, "BACK") # Shift+Tab
        
        # Shift+Enter / Newline logic (LF = 10)
        if k == 10 or k == 337 or k == 525:
            if multiline:
                query = query[:cursor_idx] + "\n" + query[cursor_idx:]
                cursor_idx += 1
                continue
            else: return (query, "NEXT")
            
        if k == 27:
            k2 = stdscr.getch()
            if k2 == curses.KEY_LEFT: return (query, "BACK")
            if k2 == curses.KEY_RIGHT: return (query, "NEXT")
            if k2 in [10, 13]: # Alt+Enter
                if multiline:
                    query = query[:cursor_idx] + "\n" + query[cursor_idx:]
                    cursor_idx += 1; continue
            if k2 == -1: return (None, "CANCEL")
            
        # Editing
        elif k in [127, 8, curses.KEY_BACKSPACE]:
            if cursor_idx > 0:
                query = query[:cursor_idx-1] + query[cursor_idx:]
                cursor_idx -= 1
        elif k == curses.KEY_DC:
            if cursor_idx < len(query):
                query = query[:cursor_idx] + query[cursor_idx+1:]
        
        # Arrows (Visual movement)
        elif k == curses.KEY_LEFT:
            if cursor_idx > 0: cursor_idx -= 1
        elif k == curses.KEY_RIGHT:
            if cursor_idx < len(query): cursor_idx += 1
        elif k == curses.KEY_UP:
            # Move cursor back by one visual line length
            cursor_idx = max(0, cursor_idx - avail_w)
        elif k == curses.KEY_DOWN:
            cursor_idx = min(len(query), cursor_idx + avail_w)
            
        elif 32 <= k <= 126:
            query = query[:cursor_idx] + chr(k) + query[cursor_idx:]
            cursor_idx += 1
            
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
        
        if k == 9: return (matches[sel_idx] if matches else None, "NEXT")   # TAB
        if k == 353: return (None, "BACK") # Shift+Tab
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
    
    cfg = storage.load_config()
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
        attr = curses.color_pair(color_id) | curses.A_REVERSE | curses.A_BOLD
        for y in range(cy, cy + card_h): safe_addstr(stdscr, y, cx, " " * card_w, attr)
        safe_addstr(stdscr, cy+1, cx+2, f"  {title}  ", curses.color_pair(0)|curses.A_BOLD)
        
        # Navigation Bar
        nav_msg = "[Tab/Ent] Next  [S-Tab] Back  [Esc] Cancel  [S-Ent] NewLine"
        safe_addstr(stdscr, h-2, (w - len(nav_msg)) // 2, nav_msg, curses.color_pair(4) | curses.A_BOLD)
        return attr

    while 0 <= cur_step < len(steps):
        step = steps[cur_step]
        
        if step == 'PROJECT':
            sel_idx = 0
            scroll_idx = 0
            query = ""
            
            while True:
                # Filter matches
                if query:
                    matches = [p for p in all_projs if query.lower() in p.lower()]
                    if query not in matches:
                        matches.insert(0, f"+ CREATE: {query}")
                else:
                    matches = all_projs[:]
                
                # Determine preview info
                if matches and 0 <= sel_idx < len(matches):
                    p_name = matches[sel_idx]
                    if p_name.startswith("+ CREATE: "): p_name = p_name[10:]
                else:
                    p_name = query if query else "General"
                
                c_id = p_colors.get(p_name, 4)
                if p_name == "+ NEW PROJECT" or p_name not in p_colors: c_id = 0
                
                main_attr = draw_base_card(c_id, "STEP 1: SELECT PROJECT")
                
                # Search Bar
                safe_addstr(stdscr, cy+3, cx+4, f"SEARCH: {query}", main_attr)
                safe_addstr(stdscr, cy+3, cx+12+len(query), "_", main_attr | curses.A_BLINK)
                
                # List with Scroll
                list_h = max(5, card_h - 8)
                if sel_idx < scroll_idx: scroll_idx = sel_idx
                elif sel_idx >= scroll_idx + list_h: scroll_idx = sel_idx - list_h + 1
                
                for i in range(list_h):
                    ii = scroll_idx + i
                    if ii >= len(matches): break
                    p = matches[ii]
                    
                    is_sel = (ii == sel_idx)
                    attr = curses.A_REVERSE if is_sel else 0
                    
                    # Resolve color
                    clean_p = p[10:] if p.startswith("+ CREATE: ") else p
                    if clean_p == "+ NEW PROJECT": clean_p = "General"
                    
                    p_col = p_colors.get(clean_p, 0)
                    if is_sel: attr |= curses.color_pair(0)
                    elif p_col: attr |= curses.color_pair(p_col)
                    
                    safe_addstr(stdscr, cy+5+i, cx+4, f" {p[:card_w-10]} ", attr)
                
                stdscr.refresh()
                k = stdscr.getch()
                
                if k == 27: return None
                elif k == 542: return None
                elif k == curses.KEY_UP: sel_idx = max(0, sel_idx - 1)
                elif k == curses.KEY_DOWN: sel_idx = min(len(matches)-1, sel_idx + 1)
                elif k in [curses.KEY_BACKSPACE, 127, 8]:
                    query = query[:-1]
                    sel_idx = 0
                elif 32 <= k <= 126:
                    query += chr(k)
                    sel_idx = 0
                elif k in [10, 13]:
                    if not matches and query:
                         state['project'] = query
                         state['color_id'] = select_color(stdscr, cy+6, cx+4) or 4
                         add_project(state['project'], state['color_id'], [])
                         cur_step += 1; break
                    elif matches:
                        sel_p = matches[sel_idx]
                        if sel_p.startswith("+ CREATE: "):
                            new_p = sel_p[10:]
                            state['project'] = new_p
                            state['color_id'] = select_color(stdscr, cy+6, cx+4) or 4
                            add_project(state['project'], state['color_id'], [])
                        elif sel_p == "+ NEW PROJECT":
                             res, _ = text_input(stdscr, cy+4, cx+4, "NEW PROJECT NAME:")
                             if res:
                                 state['project'] = res
                                 state['color_id'] = select_color(stdscr, cy+6, cx+4) or 4
                                 add_project(state['project'], state['color_id'], [])
                             else: continue
                        else:
                            state['project'] = sel_p
                            state['color_id'] = p_colors.get(sel_p, 4)
                        cur_step += 1; break

        elif step == 'NAME':
            main_attr = draw_base_card(state['color_id'], f"PROJECT: {state['project'].upper()}")
            res, action = card_text_input(stdscr, cy+5, cx+4, "TASK NAME:", main_attr, prefill=state['content'], max_width=card_w-8)
            if action == "CANCEL": return None
            state['content'] = res or ""
            cur_step += (1 if action == "NEXT" else -1)

        elif step == 'DESCRIPTION':
            main_attr = draw_base_card(state['color_id'], f"PROJECT: {state['project'].upper()}")
            safe_addstr(stdscr, cy+5, cx+4, f"NAME: {state['content']}", main_attr)
            res, action = card_text_input(stdscr, cy+7, cx+4, "DESCRIPTION:", main_attr, prefill=state['description'], max_width=card_w-8, multiline=True)
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
            
            # Use unified nav bar hint
            nav_msg = "[S-Tab] Back  [Enter] Save  [Esc] Discard"
            safe_addstr(stdscr, h-2, (w - len(nav_msg)) // 2, nav_msg, curses.color_pair(4) | curses.A_BOLD)
            
            stdscr.refresh()
            stdscr.nodelay(True)
            while True:
                k = stdscr.getch()
                if k == -1: time.sleep(0.02); continue
                
                if k in [10, 13, 9]: # Enter or Tab to confirm
                    add_todo(state['content'], state['date'], state['project'], state['tags'], state['description'])
                    return state['project']
                
                if k in [353, 542]: # Shift+Tab or Alt+Left
                    cur_step -= 1; break
                    
                if k == 27:
                    # Check for Alt sequence
                    k2 = stdscr.getch()
                    if k2 == curses.KEY_LEFT or k2 == 542:
                        cur_step -= 1; break
                    if k2 == -1: return None # True ESC
            stdscr.nodelay(False)
    return None

def edit_todo_dialog(stdscr, item):
    h, w = stdscr.getmaxyx()
    # State copy
    state = item.copy()
    # Ensure all keys exist
    for k in ['content', 'description', 'date', 'project', 'tags', 'status']:
        if k not in state: state[k] = "" if k != 'tags' else []
    if 'tags' not in state or state['tags'] is None: state['tags'] = []
    
    cfg = storage.load_config()
    p_colors = cfg.get('project_colors', {})
    
    fields = ['PROJECT', 'DATE', 'TAGS', 'CONTENT', 'DESCRIPTION', 'SAVE']
    active_idx = 0
    
    while True:
        tick_timer(); stdscr.erase(); draw_pip_timer(stdscr)
        
        # Draw Card
        draw_neobrutalist_card(stdscr, state, p_colors, fields[active_idx])
        
        # Save Button Hint
        if fields[active_idx] == 'SAVE':
            msg = " PRESS [ENTER] TO SAVE CHANGES "
            safe_addstr(stdscr, h-2, (w-len(msg))//2, msg, curses.color_pair(2)|curses.A_BOLD|curses.A_REVERSE)
        else:
            safe_addstr(stdscr, h-2, 2, "[TAB] Next Field  [ENTER] Edit Field  [ESC] Cancel", curses.A_DIM)
            
        stdscr.refresh()
        k = stdscr.getch()
        
        if k == 9: # TAB
            active_idx = (active_idx + 1) % len(fields)
        elif k == 353: # Shift+TAB (approx)
            active_idx = (active_idx - 1) % len(fields)
        elif k == 27: return False # Cancel
        elif k in [10, 13]: # Enter
            field = fields[active_idx]
            
            if field == 'CONTENT':
                res, _ = text_input(stdscr, h//2, w//2 - 20, "EDIT CONTENT:", state['content'])
                if res: state['content'] = res
            
            elif field == 'DESCRIPTION':
                res, _ = text_input(stdscr, h//2, w//2 - 20, "EDIT DESCRIPTION:", state['description'])
                if res is not None: state['description'] = res
            
            elif field == 'DATE':
                res, action = select_date_dialog(stdscr, h//2, w//2 - 20)
                if action != 'CANCEL': state['date'] = res
            
            elif field == 'PROJECT':
                projs = ["General"] + get_unique_projects() + ["+ NEW PROJECT"]
                p, _ = fuzzy_select(stdscr, h//2, w//2 - 20, "SELECT PROJECT", projs)
                if p == "+ NEW PROJECT":
                    new_p, _ = text_input(stdscr, h//2, w//2 - 20, "NEW PROJECT NAME:")
                    if new_p:
                        state['project'] = new_p
                        add_project(new_p)
                elif p:
                    state['project'] = p
            
            elif field == 'TAGS':
                proj_tags = get_project_tags(state['project'])
                res, action = multi_select_tags(stdscr, h//2, w//2 - 20, "EDIT TAGS", proj_tags, selected=state['tags'])
                if action != 'CANCEL': state['tags'] = res
            
            elif field == 'SAVE':
                update_todo(item['id'], state['content'], state['date'], state['project'], state['tags'], state['description'])
                return True
                
    return False

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
