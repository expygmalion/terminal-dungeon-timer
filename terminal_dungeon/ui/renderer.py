import curses
import time
from datetime import datetime
import textwrap
from .. import state
from ..config import BIG_FONT

def safe_addstr(stdscr, y, x, text, attr=0):
    try: 
        stdscr.addstr(y, x, text[:stdscr.getmaxyx()[1]-x-1], attr)
    except: pass

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

def format_duration(seconds):
    m = int(seconds // 60); s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def draw_pip_timer(stdscr):
    if not state.TIMER.is_active: return
    h, w = stdscr.getmaxyx()
    
    proj = state.TIMER.project
    task = state.TIMER.task
    xp = state.TIMER.duration_secs // 60
    
    width = max(30, min(w-4, len(task) + 4), min(w-4, len(proj) + 15))
    height = 5
    
    y = h - 6
    x = (w - width) // 2
    
    if y < 0: return

    if state.TIMER.state_name == 'running': elapsed = state.TIMER.elapsed_before_pause + (time.time() - state.TIMER.start_time)
    else: elapsed = state.TIMER.elapsed_before_pause
    rem = max(0, state.TIMER.duration_secs - elapsed); t_str = format_duration(rem)
    
    color = curses.color_pair(4)
    if state.TIMER.state_name == 'paused': color = curses.color_pair(6)
    elif state.TIMER.state_name == 'finished': color = curses.color_pair(2)
    
    try:
        draw_box(stdscr, y, x, height, width, "ACTIVE TIMER")
        
        header = f"{proj[:20]} | {int(xp)} XP"
        safe_addstr(stdscr, y+1, x+2, header, curses.A_BOLD | curses.color_pair(2))
        
        safe_addstr(stdscr, y+2, x+2, task[:width-4])
        
        icon = "▶" if state.TIMER.state_name=='running' else ("⏸" if state.TIMER.state_name=='paused' else "✔")
        safe_addstr(stdscr, y+3, x + (width - len(t_str) - 4)//2, f"{icon} {t_str}", color | curses.A_BOLD)
    except: pass

def draw_neobrutalist_card(stdscr, item, p_colors, active_field=None):
    h, w = stdscr.getmaxyx()
    card_w, card_h = min(84, int(w * 0.9)), min(26, int(h * 0.9))
    cy, cx = (h - card_h) // 2, (w - card_w) // 2
    
    p_name = item.get('project', 'General')
    p_col_id = p_colors.get(p_name, 4)
    
    # Body
    main_attr = curses.color_pair(p_col_id) | curses.A_REVERSE | curses.A_BOLD
    for y in range(cy, cy + card_h): safe_addstr(stdscr, y, cx, " " * card_w, main_attr)
        
    # Stickers
    st_attr = curses.color_pair(0) | curses.A_BOLD
    p_attr = st_attr | curses.A_REVERSE if active_field == 'PROJECT' else st_attr
    safe_addstr(stdscr, cy+1, cx+2, f"  {p_name.upper()}  ", p_attr)
    
    d_attr = st_attr | curses.A_REVERSE if active_field == 'DATE' else st_attr
    safe_addstr(stdscr, cy+2, cx+4, f" {item.get('date', 'NA')} ", d_attr)
    
    status = item.get('status', 'PENDING').upper()
    s_col = curses.color_pair(2 if status == 'DONE' or status == 'COMPLETED' else 5)
    safe_addstr(stdscr, cy+1, cx+card_w-len(status)-6, f" {status} ", s_col | curses.A_BOLD | curses.A_REVERSE)
    
    # Dynamic Meta Label
    meta = item.get('meta_label', " REWARD: 30 XP ")
    safe_addstr(stdscr, cy+2, cx+card_w-len(meta)-4, meta, st_attr)
    
    # Tags
    tags = item.get('tags', [])
    t_str = " ".join([f"#{t}" for t in tags]) if tags else "NO TAGS"
    if len(t_str) > card_w - 8: t_str = t_str[:card_w-11] + "..."
    t_attr = st_attr | curses.A_REVERSE if active_field == 'TAGS' else st_attr
    safe_addstr(stdscr, cy+3, cx+4, t_str, t_attr)
    
    # Content
    c_attr = main_attr | curses.color_pair(4) if active_field == 'CONTENT' else main_attr
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

    for i, line in enumerate(lines[:5]): safe_addstr(stdscr, cy+5+i, cx+4, line, c_attr)
    
    desc = item.get('description', '')
    if desc or active_field == 'DESCRIPTION':
        safe_addstr(stdscr, cy+11, cx+2, "▀" * (card_w-4), main_attr)
        desc_h_attr = main_attr | curses.A_UNDERLINE
        if active_field == 'DESCRIPTION': desc_h_attr |= curses.color_pair(4)
        safe_addstr(stdscr, cy+12, cx+4, "DESCRIPTION:", desc_h_attr)
        
        desc_b_attr = main_attr
        if active_field == 'DESCRIPTION': desc_b_attr |= curses.color_pair(4)
        
        d_lines = []
        raw_d_lines = desc.split('\n')
        for r_line in raw_d_lines:
            while len(r_line) > inner_w:
                split = r_line[:inner_w].rfind(' ')
                if split == -1: split = inner_w
                d_lines.append(r_line[:split])
                r_line = r_line[split:].strip()
            d_lines.append(r_line)
            
        for i, line in enumerate(d_lines[:8]): safe_addstr(stdscr, cy+14+i, cx+4, line, desc_b_attr)

def draw_todo_tree(stdscr, tree, sel_idx, scroll_idx, today_str, p_colors, delete_pending_idx):
    h, w = stdscr.getmaxyx()
    bottom_margin = 5
    if state.TIMER.is_active: bottom_margin = 11
    
    sel_idx = max(0, min(sel_idx, len(tree)-1))
    if sel_idx < scroll_idx: scroll_idx = sel_idx
    
    if not tree: 
        safe_addstr(stdscr, 4, 4, "No tasks found.", curses.A_DIM)
        return scroll_idx
    
    y = 4
    max_y = h - bottom_margin
    sel_idx_visible = False
    
    wrapper = textwrap.TextWrapper(width=max(10, w - 12))
    
    for i in range(len(tree) - scroll_idx):
        ii = scroll_idx + i
        if y >= max_y: break
        
        node = tree[ii]
        is_sel = (ii == sel_idx)
        attr = curses.A_REVERSE if is_sel else 0
        if is_sel: sel_idx_visible = True
        
        # Margin Asterisk
        show_ast = False
        ast_col = 5
        if node['type'] == 'item':
            if node['data'].get('focused', False):
                 pass 
            elif node['data']['status'] == 'pending': 
                show_ast = True; ast_col = p_colors.get(node['data'].get('project', 'General'), 5)
        elif node['type'] in ['project', 'date_group', 'group']:
            if node['done'] < node['total']: 
                show_ast = True; ast_col = p_colors.get(node.get('key', node.get('parent', 'General')), 5)
        
        if show_ast:
            try: col_p = curses.color_pair(ast_col)
            except: col_p = curses.color_pair(5)
            safe_addstr(stdscr, y, 0, "\U0001F7BA", col_p)

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
            icon = "[-]" if k in state.TODO_STATE['expanded_daily'] else "[+]"
            is_past_pending = k < today_str and node['done'] < node['total']
            h_attr = curses.color_pair(5)|curses.A_BOLD if is_past_pending else curses.color_pair(4)
            safe_addstr(stdscr, y, 2, f"{icon} {lbl:<25} {pct:>3}%", attr|h_attr)
            y += 1
        
        elif node['type'] == 'project':
            k = node['key']
            pct = int((node['done']/node['total'])*100) if node['total'] > 0 else 0
            is_open = k in state.TODO_STATE['expanded_project']
            icon = "[-]" if is_open else "[+]"
            col = curses.color_pair(p_colors.get(k, 3))
            safe_addstr(stdscr, y, 2, f"{icon} {k:<25} {pct:>3}%", attr|col|curses.A_BOLD)
            y += 1
            
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
            safe_addstr(stdscr, y, 2, line, col)
            safe_addstr(stdscr, y, 6, f"{lbl:<23} {pct:>3}%", attr|d_attr)
            y += 1

        elif node['type'] == 'item':
            item = node['data']
            st = "[x]" if item['status']=='done' else "[ ]"
            is_overdue = (item.get('date', '9999-99-99') < today_str) and (item['status'] == 'pending')
            col = curses.color_pair(2) if item['status'] == 'done' else (curses.color_pair(5) if is_overdue else 0)
            
            # Focus Highlighting
            if item.get('focused', False):
                 p_name = item.get('project', 'General')
                 p_col_id = p_colors.get(p_name, 0)
                 col = curses.color_pair(p_col_id) | curses.A_REVERSE if p_col_id else curses.A_REVERSE

            t_str = " " + " ".join([f"#{t}" for t in item.get('tags', []) if t])
            
            if state.TODO_STATE['mode'] == 'DAILY':
                p_name = item.get('project', 'General')
                if p_name != "General" and not is_overdue and item['status'] != 'done' and not item.get('focused', False):
                    try: col = curses.color_pair(p_colors.get(p_name, 0))
                    except: pass
                
                content_text = f"{('╌╌ ' if is_overdue else '   ')}{st} {p_name}: {item['content']}{t_str}"
                lines = wrapper.wrap(content_text)
                for li, line_text in enumerate(lines):
                    if y >= max_y: break
                    safe_addstr(stdscr, y, 4 if li==0 else 8, line_text, attr|col)
                    y += 1
            else:
                p_name = node.get('parent', '').split('|')[0]
                t_col = curses.color_pair(p_colors.get(p_name, 3))
                
                tree_char_1 = '│' if not node.get('parent_last') else ' '
                tree_char_2 = '├' if not node.get('is_last') else '└'
                status_char = '╌' if item['status'] == 'pending' else '─'
                
                prefix = f"  {tree_char_1}  {tree_char_2}{status_char}"
                
                content_text = f"{st} {item['content']}{t_str}"
                lines = wrapper.wrap(content_text)
                
                for li, line_text in enumerate(lines):
                    if y >= max_y: break
                    if li == 0:
                        safe_addstr(stdscr, y, 2, prefix, t_col)
                        safe_addstr(stdscr, y, 9, line_text, attr|col)
                    else:
                        # Continuation
                        cont_char = '│' if not node.get('is_last') else ' '
                        cont_prefix = f"  {tree_char_1}  {cont_char} "
                        safe_addstr(stdscr, y, 2, cont_prefix, t_col)
                        safe_addstr(stdscr, y, 9, line_text, attr|col)
                    y += 1
            
        if ii == delete_pending_idx:
            # Draw on the last line of the item (y is already incremented)
            safe_addstr(stdscr, y-1, w-25, " PRESS 'D' AGAIN TO DELETE ", curses.color_pair(5)|curses.A_BOLD|curses.A_REVERSE)
            
    if not sel_idx_visible and sel_idx >= scroll_idx and len(tree) > 0:
        return scroll_idx + 1
        
    return scroll_idx

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
        if curses.COLORS > 200:
            curses.init_pair(pair_id, xterm_256_map[i], -1)
        else:
            curses.init_pair(pair_id, std_colors[i], -1)
