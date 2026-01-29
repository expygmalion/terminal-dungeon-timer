import uuid
import time
from datetime import datetime
from . import storage
from . import state
from .logic import clean_tags, calculate_stats

# --- Todo Actions ---
def add_todo(content, date_str, project, tags, description=""):
    todos = storage.load_todos()
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
    storage.save_todos(todos)

def complete_matching_todo(project, content):
    todos = storage.load_todos()
    changed = False
    for t in todos:
        if t.get('project') == project and t.get('content') == content and t.get('status') == 'pending':
            t['status'] = 'done'
            changed = True
    if changed: storage.save_todos(todos)

def toggle_todo(todo_id, duration_mins=30):
    todos = storage.load_todos()
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
        # Direct save to history
        save_session_data(session)
        target['last_session_id'] = sess_id
        
    else:
        # Switch back to PENDING
        target['status'] = 'pending'
        
        # Remove the auto-added session if it exists
        sid = target.get('last_session_id')
        if sid:
            history = storage.load_history()
            new_history = [h for h in history if h.get('id') != sid]
            if len(history) != len(new_history):
                storage.save_history(new_history)
            # Remove the link
            del target['last_session_id']
            
    storage.save_todos(todos)

def delete_todo(todo_id):
    todos = storage.load_todos()
    item = next((t for t in todos if t['id'] == todo_id), None)
    if item:
        state.UNDO_STACK.append({'type': 'todo', 'data': item})
        todos = [t for t in todos if t['id'] != todo_id]
        storage.save_todos(todos)

def update_todo(todo_id, content, date_str, project, tags, description):
    todos = storage.load_todos()
    for t in todos:
        if t['id'] == todo_id:
            t['content'] = content
            t['date'] = date_str
            t['project'] = project
            t['tags'] = clean_tags(tags)
            t['description'] = description
            break
    storage.save_todos(todos)

# --- Project Actions ---
def add_project(name, color_id=None, tags=None):
    if not name: return
    cfg = storage.load_config()
    
    if name not in cfg['project_tags']:
        cfg['project_tags'][name] = tags if tags else []
    elif tags: 
        cfg['project_tags'][name] = tags

    if color_id:
            if 'project_colors' not in cfg: cfg['project_colors'] = {}
            cfg['project_colors'][name] = color_id
    storage.save_config(cfg)

def delete_project(name):
    if name == "General": return # Protect General
    
    # 1. Remove from Config
    cfg = storage.load_config()
    if name in cfg['project_tags']:
        col = cfg.get('project_colors', {}).get(name)
        state.UNDO_STACK.append({'type': 'project', 'data': {'name': name, 'tags': cfg['project_tags'][name], 'color': col}})
        del cfg['project_tags'][name]
        if 'project_colors' in cfg and name in cfg['project_colors']:
            del cfg['project_colors'][name]
        storage.save_config(cfg)
    
    # 2. Remove from Todos
    todos = storage.load_todos()
    new_todos = [t for t in todos if t.get('project') != name]
    if len(todos) != len(new_todos):
        storage.save_todos(new_todos)

    # 3. Remove from History
    history = storage.load_history()
    new_history = [h for h in history if h.get('project') != name]
    if len(history) != len(new_history):
        storage.save_history(new_history)

def restore_last_deleted_item():
    if not state.UNDO_STACK: return False
    item = state.UNDO_STACK.pop()
    if item['type'] == 'todo':
        todos = storage.load_todos()
        todos.append(item['data'])
        storage.save_todos(todos)
    elif item['type'] == 'project':
        cfg = storage.load_config()
        p_name = item['data']['name']
        p_tags = item['data']['tags']
        cfg['project_tags'][p_name] = p_tags
        if item['data'].get('color'):
             if 'project_colors' not in cfg: cfg['project_colors'] = {}
             cfg['project_colors'][p_name] = item['data']['color']
        storage.save_config(cfg)
    return True

# --- History/Session Actions ---
def save_session_data(session):
    history = storage.load_history()
    history.insert(0, session)
    history = history[:1000]
    storage.save_history(history)

def delete_session(index):
    history = storage.load_history()
    if 0 <= index < len(history):
        del history[index]
        storage.save_history(history)
        return True
    return False

# --- Timer Logic ---
def tick_timer():
    if not state.SESSION['active'] or state.SESSION['state'] != 'running': return
    now = time.time()
    elapsed = state.SESSION['elapsed_before_pause'] + (now - state.SESSION['start_time'])
    remaining = state.SESSION['duration_secs'] - elapsed
    if now - state.SESSION['last_blink'] > 0.5:
        state.SESSION['show_colon'] = not state.SESSION['show_colon']
        state.SESSION['last_blink'] = now
    if remaining <= 0:
        state.SESSION['state'] = 'finished'; state.SESSION['show_colon'] = True
        save_session_data({"project": state.SESSION['project'], "task": state.SESSION['task'], "duration_minutes": state.SESSION['duration_secs'] // 60, "timestamp": datetime.now().isoformat(), "status": "completed"})
        complete_matching_todo(state.SESSION['project'], state.SESSION['task'])

def start_new_session(project, task, duration_mins):
    state.SESSION['active'] = True; state.SESSION['state'] = 'running'
    state.SESSION['project'] = project; state.SESSION['task'] = task
    state.SESSION['duration_secs'] = duration_mins * 60
    state.SESSION['start_time'] = time.time(); state.SESSION['elapsed_before_pause'] = 0; state.SESSION['show_colon'] = True

def terminate_session():
    if not state.SESSION['active']: return
    elapsed = state.SESSION['elapsed_before_pause']
    if state.SESSION['state'] == 'running': elapsed += (time.time() - state.SESSION['start_time'])
    if state.SESSION['state'] != 'finished':
        save_session_data({"project": state.SESSION['project'], "task": state.SESSION['task'], "duration_minutes": state.SESSION['duration_secs'] // 60, "timestamp": datetime.now().isoformat(), "status": "terminated", "actual_duration_seconds": int(elapsed)})
    state.SESSION['active'] = False; state.SESSION['state'] = 'stopped'

def pause_timer():
    if state.SESSION['state'] == 'running':
        state.SESSION['state'] = 'paused'
        state.SESSION['elapsed_before_pause'] += (time.time() - state.SESSION['start_time'])

def resume_timer():
    if state.SESSION['state'] == 'paused':
        state.SESSION['state'] = 'running'
        state.SESSION['start_time'] = time.time()
