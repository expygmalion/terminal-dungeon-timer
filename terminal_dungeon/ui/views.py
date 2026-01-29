import curses
import sys
import time
from datetime import datetime, timedelta
import textwrap

from .. import storage, state, controller
from ..logic import calculate_stats, determine_class, get_unique_projects, get_unique_tasks, format_duration
from .renderer import safe_addstr, draw_box, draw_big_text, draw_pip_timer, draw_neobrutalist_card, draw_todo_tree
from .inputs import select_duration, select_color, fuzzy_select, text_input, add_new_todo_dialog, edit_todo_dialog, tag_filtering_dialog, select_date_dialog

def check_nav_keys(key):
    if key in [ord('h'), ord('H')]: return 'HEATMAP'
    if key in [ord('w'), ord('W')]: return 'WEEKLY'
    if key in [ord('r'), ord('R')]: return 'RAID'
    if key in [ord('i'), ord('I')]: return 'INFO'
    if key in [ord('p'), ord('P')]: return 'SETTINGS'
    if key in [ord('T')]: return 'TIMER'
    if key in [ord('l'), ord('L')]: return 'TODO'
    return None

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
        controller.tick_timer(); stdscr.erase(); draw_pip_timer(stdscr)
        cfg = storage.load_config()
        p_colors = cfg.get('project_colors', {})
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Render Todo List Tabs/Header
        mode = state.TODO_STATE['mode']
        tabs = f" [{'DAILY' if mode=='DAILY' else '  DAILY  '}] " + f" [{'PROJECT' if mode=='PROJECT' else '  PROJECT  '}] "
        safe_addstr(stdscr, 1, 2, tabs, curses.color_pair(3)|curses.A_BOLD)
        safe_addstr(stdscr, 2, 2, "="*(w-4), curses.color_pair(3))
        
        draw_todo_tree(stdscr, tree, idx, scroll_idx, today_str, p_colors, -1)
        
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
        elif k in [ord('f'), ord('F')]:
            # Toggle Focus
            if item.get('id') != 'history':
                todos_all = storage.load_todos()
                changed = False
                for t in todos_all:
                    if t['id'] == item['id']:
                        t['focused'] = not t.get('focused', False)
                        # Update local item to reflect change immediately
                        item['focused'] = t['focused']
                        tree[idx]['data']['focused'] = t['focused']
                        changed = True; break
                if changed: storage.save_todos(todos_all)
        elif k in [10, 13, 529]:
            # Guard against history items or non-toggleable items
            if item.get('id') == 'history': return idx 
            
            dur = 15
            if k in [10, 529]:
                dur = select_duration(stdscr)
                if dur is None: dur = 0
            if dur > 0:
                controller.toggle_todo(item['id'], dur)
                try:
                    tree[idx]['data'] = next(t for t in storage.load_todos() if t['id'] == item['id'])
                except: pass

def show_history(stdscr):
    idx = 0; scroll = 0; use_nerd = "--nerd-fonts" in sys.argv
    history = storage.load_history(); last_load = time.time(); stdscr.timeout(50)
    cfg = storage.load_config()
    
    view_mode = 'TODAY' # 'TODAY' or 'ALL'
    current_date = datetime.now().date()
    
    while True:
        def render(draw_scroll, draw_idx):
            controller.tick_timer()
            stdscr.erase(); h, w = stdscr.getmaxyx()
            
            # Filter History based on Mode
            display_history_local = []
            if view_mode == 'ALL':
                display_history_local = history
                title_str = "ALL HISTORY"
            else:
                display_history_local = [
                    x for x in history 
                    if x.get('timestamp') and datetime.fromisoformat(x['timestamp']).date() == current_date
                ]
                title_str = f"HISTORY: {current_date.strftime('%a %d %b %Y').upper()}"

            tt, ty, ratio = calculate_stats(history)
            
            # Header
            safe_addstr(stdscr, 0, 2, f"{title_str:<30} | TODAY: {tt:.1f}m | YEST: {ty:.1f}m", curses.color_pair(2)|curses.A_BOLD)
            
            # Table Header
            if use_nerd:
                header = f"{ ' TIME':<6} | { ' PROJECT':<12} | { ' TASK':<25} | { ' DUR':<5} | { ' STATUS':<10} | {' MULT'}"
            else:
                header = f"{ 'TIME':<6} | {'PROJECT':<12} | {'TASK':<25} | {'DUR':<5} | {'STATUS':<10} | {'MULT'}"
            safe_addstr(stdscr, 2, 2, header, curses.color_pair(3)); safe_addstr(stdscr, 3, 2, "-"*min(len(header), w-2), curses.color_pair(3))
            
            list_h_local = max(1, h - 6)
            
            # Table Content
            if not display_history_local:
                safe_addstr(stdscr, 4, 2, "No sessions found for this period.", curses.A_DIM)
            else:
                p_colors = cfg.get('project_colors', {})
                for i in range(list_h_local):
                    ii = draw_scroll + i
                    if ii >= len(display_history_local): break
                    it = display_history_local[ii]; st = "SUCCESS" if it.get('status')=='completed' else "TERM"
                    dm = f"{it.get('duration_minutes',0)}m" if st=="SUCCESS" else f"{int(it.get('actual_duration_seconds',0)//60)}m"
                    
                    ts = it.get('timestamp', '')
                    tm_str = ts[11:16] if len(ts) >= 16 else "--:--"
                    
                    p_name = it.get('project', '-')
                    p_color_id = p_colors.get(p_name, 0)
                    
                    if use_nerd: st = " SUCCESS" if st=="SUCCESS" else " TERM"
                    
                    # Selection vs Row attribute
                    attr = curses.color_pair(0) | curses.A_REVERSE if ii == draw_idx else (curses.color_pair(p_color_id) if p_color_id else 0)
                    
                    row_str = f"{tm_str:<6} | {p_name[:12]:<12} | {it.get('task','-')[:25]:<25} | {dm:<5} | {st[:10]:<10} | {'1.0x' if st.endswith('SUCCESS') else '-'}"
                    safe_addstr(stdscr, 4+i, 2, row_str, attr)
            
            # Footer Help
            nav_help = "[TAB] View  [[] Day -  []] Day +  [Space] Dtls  [N] New  [L] Todo  [D] Del"
            safe_addstr(stdscr, h-1, 2, f"{nav_help}  [H] Heat  [W] Week  [R] Raid  [P] Pref  [Q] Quit", curses.color_pair(4))
            
            draw_pip_timer(stdscr)
            return display_history_local, list_h_local

        if time.time() - last_load > 1.0: history = storage.load_history(); last_load = time.time()
        
        display_history, list_h = render(scroll, idx)
        
        if not display_history: idx = 0
        else: idx = max(0, min(idx, len(display_history) - 1))
        
        if idx < scroll: scroll = idx
        elif idx >= scroll + list_h: scroll = idx - list_h + 1
        
        stdscr.refresh(); k = stdscr.getch()
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
                    if rh.id == target_item.id: # Use ID for matching object now
                        real_idx = ri; break
                if real_idx != -1:
                    controller.delete_session(real_idx); history = storage.load_history()
        if k in [ord('q'), ord('Q')]: return 'QUIT'
        elif k == curses.KEY_UP: idx -= 1
        elif k == curses.KEY_DOWN: idx += 1
        elif k == ord(' ') and display_history:
             curr_idx = idx
             while True:
                 # Update scroll if needed (using estimated list_h or previous)
                 # We call render to get list_h first? No, just render.
                 _, list_h = render(scroll, curr_idx)
                 
                 # Fix scroll if cursor moved off screen
                 if curr_idx < scroll: 
                     scroll = curr_idx
                     _, list_h = render(scroll, curr_idx)
                 elif curr_idx >= scroll + list_h: 
                     scroll = curr_idx - list_h + 1
                     _, list_h = render(scroll, curr_idx)
                 
                 # Get Item Data
                 if 0 <= curr_idx < len(display_history):
                     item = display_history[curr_idx]
                     mock_data = {
                         'id': item.get('id', 'history'),
                         'project': item.get('project', 'General'),
                         'content': item.get('task', 'No Task'),
                         'date': datetime.fromisoformat(item['timestamp']).strftime("%Y-%m-%d"),
                         'status': 'DONE' if item.get('status')=='completed' else 'TERM',
                         'tags': [], 
                         'meta_label': f" DURATION: {item.get('duration_minutes', 0) if item.get('status')=='completed' else int(item.get('actual_duration_seconds',0)/60)}m ",
                         'description': f"Logged on: {datetime.fromisoformat(item['timestamp']).strftime('%Y-%m-%d %H:%M')}"
                     }
                     draw_neobrutalist_card(stdscr, mock_data, cfg.get('project_colors', {}))
                 
                 curses.curs_set(0)
                 stdscr.refresh()
                 k2 = stdscr.getch()
                 
                 if k2 in [ord(' '), 27]: break
                 elif k2 == curses.KEY_UP: curr_idx = max(0, curr_idx - 1)
                 elif k2 == curses.KEY_DOWN: curr_idx = min(len(display_history)-1, curr_idx + 1)
                 
                 time.sleep(0.05)
             
             idx = curr_idx

def show_settings(stdscr):
    cfg = storage.load_config(); opts = ["Manage Projects", "Manage Classes", "Save & Return"]
    sel = 0
    while True:
        controller.tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
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
                        new_p, _ = text_input(stdscr, h//2, w//2 - 20, "PROJECT NAME:")
                        if new_p: controller.add_project(new_p); cfg = storage.load_config()
                    elif p:
                        act, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, f"MANAGE {p}", ["Edit Tags", "Edit Color", "Delete Project", "Cancel"])
                        if act == "Edit Tags":
                            curr_tags = cfg['project_tags'].get(p, [])
                            val, _ = text_input(stdscr, h//2, w//2 - 20, f"TAGS FOR '{p}' (comma sep):", ",".join(curr_tags))
                            if val is not None:
                                cfg['project_tags'][p] = [t.strip() for t in val.split(',') if t.strip()]
                                storage.save_config(cfg)
                        elif act == "Edit Color":
                            # Current color
                            c_id = cfg.get('project_colors', {}).get(p)
                            new_col = select_color(stdscr, h//2 - 5, w//2 + 22)
                            if new_col:
                                if 'project_colors' not in cfg: cfg['project_colors'] = {}
                                cfg['project_colors'][p] = new_col
                                storage.save_config(cfg)
                        elif act == "Delete Project":
                            msg = f" PERMANENTLY DELETE '{p}' + DATA? (y/n) "
                            safe_addstr(stdscr, h-1, 2, " " * (w-3))
                            safe_addstr(stdscr, h-1, 2, msg, curses.color_pair(5) | curses.A_BOLD)
                            stdscr.refresh()
                            stdscr.timeout(-1)
                            if stdscr.getch() in [ord('y'), ord('Y')]:
                                controller.delete_project(p); cfg = storage.load_config()
                            stdscr.timeout(50)
            elif sel == 1: # Manage Classes
                cls_names = [c['name'] for c in cfg['classes']] + ["+ ADD NEW CLASS"]
                c, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "SELECT CLASS", cls_names)
                if c == "+ ADD NEW CLASS":
                    name, _ = text_input(stdscr, h//2, w//2 - 20, "NEW CLASS NAME:")
                    if name:
                        tags, _ = text_input(stdscr, h//2 + 4, w//2 - 20, "KEYWORDS (comma sep):")
                        if tags:
                            cfg['classes'].append({"name": name, "tags": [t.strip() for t in tags.split(',') if t.strip()]})
                elif c:
                    cls = next((x for x in cfg['classes'] if x['name'] == c), None)
                    if cls:
                        act, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, f"MANAGE {c}", ["Edit Name", "Edit Tags", "Delete Class", "Cancel"])
                        if act == "Edit Name":
                            new_name, _ = text_input(stdscr, h//2, w//2 - 20, "NEW NAME:", cls['name'])
                            if new_name: cls['name'] = new_name
                        elif act == "Edit Tags":
                            tags, _ = text_input(stdscr, h//2, w//2 - 20, "TAGS (comma sep):", ",".join(cls['tags']))
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
                storage.save_config(cfg)
                return 'HISTORY'
        elif k == 27: return 'HISTORY'

def show_timer_view(stdscr):
    btn = 0
    focus_idx = 0
    active_section = 'CONTROLS' # 'CONTROLS' or 'FOCUS'
    
    while True:
        def render():
            controller.tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx()
            
            # Draw Focus List
            focus_list = state.TODO_STATE.get('focus_queue', [])
            todos = storage.load_todos()
            f_items_local = [t for t in todos if t.get('focused', False)]
            
            split_x = w // 2
            
            # --- LEFT SIDE: CURRENT TIMER ---
            if state.TIMER.is_active:
                cfg = storage.load_config()
                p_color_id = cfg.get('project_colors', {}).get(state.TIMER.project, 0)
                p_attr = curses.color_pair(p_color_id) if p_color_id else 0
                
                draw_box(stdscr, 1, 2, 6, split_x - 4, "DETAILS")
                safe_addstr(stdscr, 2, 4, f"PROJECT: {state.TIMER.project}", p_attr|curses.A_BOLD)
                safe_addstr(stdscr, 3, 4, f"TASK:    {state.TIMER.task}")
                
                if state.TIMER.state_name == 'running':
                     elapsed = state.TIMER.elapsed_before_pause + (time.time() - state.TIMER.start_time)
                else:
                     elapsed = state.TIMER.elapsed_before_pause
                
                rem = max(0, state.TIMER.duration_secs - elapsed); t_str = format_duration(rem)
                color = curses.color_pair(4) if state.TIMER.state_name=='running' else curses.color_pair(6)
                if state.TIMER.state_name=='finished': color = curses.color_pair(2)
                
                draw_big_text(stdscr, h//2 - 4, (split_x - 30)//2, t_str if state.TIMER.show_colon else t_str.replace(":"," "), color)
                
                # Progress Bar
                bar_y = h//2 + 5; bar_w = split_x - 10
                if bar_w > 0:
                    draw_box(stdscr, bar_y - 1, 2, 3, bar_w + 4)
                    pct = 1.0 - (rem / state.TIMER.duration_secs) if state.TIMER.duration_secs > 0 else 1.0
                    if state.TIMER.state_name == 'finished': pct = 1.0
                    fld = int(bar_w * pct)
                    safe_addstr(stdscr, bar_y, 4, "█"*fld + "░"*(bar_w-fld), curses.color_pair(3))
                
                safe_addstr(stdscr, bar_y+3, 4, f"STATUS: {state.TIMER.state_name.upper()}", color|curses.A_BOLD)

                # Controls
                btns = ["MENU", "RESTART", "QUIT"] if state.TIMER.state_name=='finished' else ["PAUSE" if state.TIMER.state_name=='running' else "RESUME", "STOP", "RESTART", "BACK", "QUIT"]
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
            return f_items_local, btns if state.TIMER.is_active else []

        f_items, btns = render()
        
        stdscr.refresh(); stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        if k == -1: time.sleep(0.05); continue
        
        nav = check_nav_keys(k); 
        if nav and nav != 'TIMER': return nav
        
        if k == 9: # TAB
            active_section = 'FOCUS' if active_section == 'CONTROLS' else 'CONTROLS'
        
        elif active_section == 'CONTROLS' and state.TIMER.is_active:
            if k == curses.KEY_LEFT: btn = max(0, btn - 1)
            elif k == curses.KEY_RIGHT: btn = min(len(btns)-1, btn + 1)
            elif k in [10, 13]:
                sel = btns[btn]
                if sel in ["BACK", "MENU"]: return 'HISTORY'
                elif sel == "QUIT": controller.terminate_session(); return 'QUIT'
                elif sel == "STOP": controller.terminate_session(); return 'HISTORY'
                elif sel == "RESTART": controller.terminate_session(); controller.start_new_session(state.TIMER.project, state.TIMER.task, state.TIMER.duration_secs//60); return 'TIMER'
                elif sel == "RESUME": controller.resume_timer()
                elif sel == "PAUSE": controller.pause_timer()
        
        elif active_section == 'FOCUS':
            if k == curses.KEY_UP: focus_idx = max(0, focus_idx - 1)
            elif k == curses.KEY_DOWN: focus_idx = min(len(f_items)-1, focus_idx + 1)
            elif k == ord(' ') and f_items:
                item = f_items[focus_idx]
                cfg = storage.load_config()
                # We need a loop that handles navigation keys and updates 'item'
                curr_f_idx = focus_idx
                while True:
                    render() # Redraw background
                    curr_item = f_items[curr_f_idx]
                    draw_neobrutalist_card(stdscr, curr_item, cfg.get('project_colors', {}))
                    curses.curs_set(0) # Ensure cursor is hidden
                    stdscr.refresh()
                    k2 = stdscr.getch()
                    if k2 in [ord(' '), 27]: break
                    elif k2 == curses.KEY_UP:
                        curr_f_idx = max(0, curr_f_idx - 1)
                    elif k2 == curses.KEY_DOWN:
                        curr_f_idx = min(len(f_items)-1, curr_f_idx + 1)
                    time.sleep(0.05)
                focus_idx = curr_f_idx

            elif k in [10, 13] and f_items:
                target = f_items[focus_idx]
                if state.TIMER.is_active: controller.terminate_session()
                d = select_duration(stdscr)
                if d:
                    controller.start_new_session(target.get('project', 'General'), target['content'], d)
                    active_section = 'CONTROLS' 

        if k == 27: return 'HISTORY'

def show_yearly_heatmap(stdscr):
    if curses.can_change_color():
        curses.init_color(20, 86, 105, 133); curses.init_color(21, 54, 266, 160); curses.init_color(22, 0, 427, 196)
        curses.init_color(23, 149, 651, 255); curses.init_color(24, 223, 827, 325)
        for i in range(20, 25): curses.init_pair(i, i, -1)
    history = storage.load_history(); yd = {}; sy = datetime.now().date() - timedelta(weeks=52); sy -= timedelta(days=sy.weekday())
    total_c = 0
    for i in history:
        try:
            d = datetime.fromisoformat(i['timestamp']).date(); dur = i['duration_minutes'] if i.get('status')=='completed' else (i.get('actual_duration_seconds',0)/60)
            if 0 <= (d - sy).days < 371: yd[((d-sy).days//7, d.weekday())] = yd.get(((d-sy).days//7, d.weekday()),0) + dur; total_c += 1
        except: pass
    while True:
        controller.tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
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
    history = storage.load_history(); now = datetime.now(); today = now.date(); curr_wk = today - timedelta(days=today.weekday())
    daily_xp = [0]*7; proj_xp = {}; wk_total = 0
    cfg = storage.load_config()
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
        controller.tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        draw_box(stdscr, 1, 0, 5, w, "PLAYER HUD")
        
        # Calculate Class
        top_p = max(proj_xp, key=proj_xp.get) if proj_xp else "Novice"
        p_class = determine_class(top_p, cfg)
        
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
    history = storage.load_history(); now = datetime.now(); today = now.date()
    todays = [i for i in history if datetime.fromisoformat(i['timestamp']).date()==today]
    todays.sort(key=lambda x: x['timestamp']); sel = len(todays)-1 if todays else 0; scr = 0
    boss_idx = -1; max_d = 0
    if todays:
        for i,s in enumerate(todays):
            d = s.get('duration_minutes',0) if s.get('status')=='completed' else s.get('actual_duration_seconds',0)/60
            if d > max_d: max_d = d; boss_idx = i
    while True:
        controller.tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
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
            
            cfg = storage.load_config()
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
        controller.tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
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

def show_todo_list(stdscr):
    # Use global state for persistence
    mode = state.TODO_STATE['mode']
    backlog_active = state.TODO_STATE['backlog_active']
    isolation_filter = state.TODO_STATE['isolation_filter']
    isolation_type = state.TODO_STATE['isolation_type']
    active_filter = state.TODO_STATE['active_filter']
    
    sel_idx = 0
    scroll_idx = 0
    delete_pending_idx = -1
    jump_target = None
    
    while True:
        controller.tick_timer(); stdscr.erase(); h, w = stdscr.getmaxyx(); draw_pip_timer(stdscr)
        # Dynamic expansion set based on mode
        expanded = state.TODO_STATE['expanded_daily'] if mode == 'DAILY' else state.TODO_STATE['expanded_project']
        
        # Update global state sync
        state.TODO_STATE['mode'] = mode
        state.TODO_STATE['backlog_active'] = backlog_active
        state.TODO_STATE['isolation_filter'] = isolation_filter
        state.TODO_STATE['isolation_type'] = isolation_type
        state.TODO_STATE['active_filter'] = active_filter

        all_todos = storage.load_todos()
        today_str = datetime.now().strftime("%Y-%m-%d")
        cfg = storage.load_config()
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
                    content_match = True 
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
            
            iso_attr = curses.color_pair(iso_col)|curses.A_REVERSE if iso_col else curses.A_REVERSE
            safe_addstr(stdscr, 1, indicator_x, f" [ISOLATED: {iso_label}] ", iso_attr|curses.A_BOLD)
            indicator_x += len(iso_label) + 14
            
        # Filter Indicator
        if active_filter:
             safe_addstr(stdscr, 1, indicator_x, " [FILTER ACTIVE] ", curses.color_pair(2)|curses.A_BOLD|curses.A_REVERSE)
            
        safe_addstr(stdscr, 2, 2, "="*(w-4), curses.color_pair(3))
        
        scroll_idx = draw_todo_tree(stdscr, tree, sel_idx, scroll_idx, today_str, p_colors, delete_pending_idx)
        
        nav_hint = "[TAB] View  [B] Backlog: " + ("ON " if backlog_active else "OFF")
        safe_addstr(stdscr, h-1, 2, f"{nav_hint}  [f] Focus  [T] Timer  [k] Today  [U] Undo  [S] Start  [F] Filter  [I] Isolate  [Space] Dtls  [Enter] Toggle  [D] Del  [ESC] Back", curses.color_pair(4))
        stdscr.refresh()
        stdscr.nodelay(True); k = stdscr.getch(); stdscr.nodelay(False)
        
        if k == -1: time.sleep(0.05); continue
        
        if k in [ord('k')]:
            if tree and 0 <= sel_idx < len(tree):
                node = tree[sel_idx]
                if node['type'] == 'item':
                    controller.move_todo_to_today(node['data']['id'])
                    # Maybe clear selection or jump? For now just refresh.
                    delete_pending_idx = -1
            continue

        if k in [ord('T')]: return 'TIMER'

        nav = check_nav_keys(k)
        if nav and nav != 'TODO' and nav != 'INFO': return nav

        if k == ord('f'):
            if tree and 0 <= sel_idx < len(tree):
                node = tree[sel_idx]
                todos_all = storage.load_todos()
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
                         # Determine target state: if all are focused, target is Unfocus. Else, target is Focus.
                         all_focused = all(t.get('focused', False) for t in todos_all if t['id'] in child_ids)
                         target_state = not all_focused
                         
                         for t in todos_all:
                             if t['id'] in child_ids:
                                 t['focused'] = target_state
                                 changed = True
                
                if changed:
                    storage.save_todos(todos_all)

        if k in [ord('s'), ord('S')]:
             if tree and 0 <= sel_idx < len(tree):
                 node = tree[sel_idx]
                 if node['type'] == 'item':
                     item = node['data']
                     d = select_duration(stdscr)
                     if d:
                         controller.start_new_session(item.get('project', 'General'), item['content'], d)
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
             controller.restore_last_deleted_item()
             delete_pending_idx = -1
        
        if k == 9: # TAB
            mode = 'PROJECT' if mode == 'DAILY' else 'DAILY'
            sel_idx = 0; scroll_idx = 0; delete_pending_idx = -1
        elif k in [curses.KEY_DOWN, ord('j')]: 
            sel_idx += 1; delete_pending_idx = -1
        elif k in [curses.KEY_UP, ord('K')]: 
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
                            controller.toggle_todo(item['id'], duration)
                    else:
                        # Toggling back to pending (no time needed)
                        controller.toggle_todo(item['id'])
            delete_pending_idx = -1
        elif k in [ord('d'), ord('D')]:
            if tree and 0 <= sel_idx < len(tree):
                node = tree[sel_idx]
                if node['type'] == 'item':
                    controller.delete_todo(node['data']['id'])
                    delete_pending_idx = sel_idx
                elif node['type'] == 'project':
                    # Optional: Prompt to confirm project deletion?
                    # For now, just delete as we have undo
                    controller.delete_project(node['key'])
        elif k in [ord('n'), ord('N')]:
            new_p = add_new_todo_dialog(stdscr); delete_pending_idx = -1
            if new_p:
                mode = 'PROJECT'

def show_quick_start_dialog(stdscr):
    stdscr.erase(); h, w = stdscr.getmaxyx()
    p, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "PROJECT", get_unique_projects())
    if not p: return 'HISTORY'
    
    # Merge pending todos + history tasks
    pending_todos = [t['content'] for t in storage.load_todos() if t.get('project') == p and t.get('status') == 'pending']
    history_tasks = get_unique_tasks(p)
    history_tasks = [t for t in history_tasks if t not in pending_todos]
    all_tasks = pending_todos + history_tasks
    
    t, _ = fuzzy_select(stdscr, h//2 - 6, w//2 - 20, "TASK", all_tasks)
    if not t: return 'HISTORY'
    
    d = select_duration(stdscr)
    if not d: return 'HISTORY'
    
    controller.start_new_session(p, t, d)
    return 'TIMER'