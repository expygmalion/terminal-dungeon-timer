import uuid
import time
from datetime import datetime
from . import storage
from . import state
from .logic import clean_tags, calculate_stats
from .model import Task, Session

def init_system():
    state.TIMER.set_callback('save_session', _save_session_callback)

def _save_session_callback(status, actual_duration, context):
    s = Session(
        project=context.project,
        task=context.task,
        duration_minutes=context.duration_secs // 60,
        status=status,
        actual_duration_seconds=actual_duration
    )
    history = storage.load_history()
    history.insert(0, s)
    history = history[:1000]
    storage.save_history(history)
    
    if status == 'completed':
        complete_matching_todo(context.project, context.task)

# Delegates
def tick_timer(): state.TIMER.tick()
def start_new_session(p, t, d): state.TIMER.start(p, t, d)
def terminate_session(): state.TIMER.stop()
def pause_timer(): state.TIMER.pause()
def resume_timer(): state.TIMER.resume()

# --- Todo Actions ---
def add_todo(content, date_str, project, tags, description=""):
    todos = storage.load_todos()
    new_todo = Task(
        content=content,
        description=description,
        date=date_str,
        project=project if project else "General",
        tags=clean_tags(tags),
        status="pending"
    )
    todos.append(new_todo)
    storage.save_todos(todos)
    state.UNDO_STACK.append({'type': 'add', 'id': new_todo.id})

def complete_matching_todo(project, content):
    todos = storage.load_todos()
    changed = False
    for t in todos:
        # t is Task object, supports .get or direct access
        if t.project == project and t.content == content and t.status == 'pending':
            t.status = 'done'
            changed = True
    if changed: storage.save_todos(todos)

def toggle_todo(todo_id, duration_mins=30, record_undo=True):
    todos = storage.load_todos()
    target = None
    for t in todos:
        if t.id == todo_id:
            target = t
            break
    
    if not target: return

    if record_undo:
        state.UNDO_STACK.append({'type': 'toggle', 'id': todo_id})

    if target.status == 'pending':
        target.status = 'done'
        
        sess_id = str(uuid.uuid4())
        session = Session(
            id=sess_id,
            project=target.project,
            task=target.content,
            duration_minutes=duration_mins,
            status="completed",
            manual_log=True
        )
        save_session_data(session)
        target.last_session_id = sess_id
        
    else:
        target.status = 'pending'
        sid = target.last_session_id
        if sid:
            history = storage.load_history()
            new_history = [h for h in history if h.id != sid]
            if len(history) != len(new_history):
                storage.save_history(new_history)
            target.last_session_id = None
            
    storage.save_todos(todos)

def delete_todo(todo_id):
    todos = storage.load_todos()
    item = next((t for t in todos if t.id == todo_id), None)
    if item:
        # UNDO stack expects dict or obj? state.undo_stack just holds data
        state.UNDO_STACK.append({'type': 'todo', 'data': item})
        todos = [t for t in todos if t.id != todo_id]
        storage.save_todos(todos)

def update_todo(todo_id, content, date_str, project, tags, description):
    todos = storage.load_todos()
    for t in todos:
        if t.id == todo_id:
            t.content = content
            t.date = date_str
            t.project = project
            t.tags = clean_tags(tags)
            t.description = description
            break
    storage.save_todos(todos)

def move_todo_to_today(todo_id):
    todos = storage.load_todos()
    today = datetime.now().strftime("%Y-%m-%d")
    for t in todos:
        if t.id == todo_id:
            t.date = today
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
    if name == "General": return
    
    cfg = storage.load_config()
    if name in cfg['project_tags']:
        col = cfg.get('project_colors', {}).get(name)
        state.UNDO_STACK.append({'type': 'project', 'data': {'name': name, 'tags': cfg['project_tags'][name], 'color': col}})
        del cfg['project_tags'][name]
        if 'project_colors' in cfg and name in cfg['project_colors']:
            del cfg['project_colors'][name]
        storage.save_config(cfg)
    
    todos = storage.load_todos()
    new_todos = [t for t in todos if t.project != name]
    if len(todos) != len(new_todos):
        storage.save_todos(new_todos)

    history = storage.load_history()
    new_history = [h for h in history if h.project != name]
    if len(history) != len(new_history):
        storage.save_history(new_history)

def restore_last_deleted_item():
    if not state.UNDO_STACK: return False
    action = state.UNDO_STACK.pop()
    
    if action['type'] == 'todo':
        todos = storage.load_todos()
        todos.append(action['data']) # item['data'] is Task object
        storage.save_todos(todos)
        
    elif action['type'] == 'project':
        cfg = storage.load_config()
        p_name = action['data']['name']
        p_tags = action['data']['tags']
        cfg['project_tags'][p_name] = p_tags
        if action['data'].get('color'):
             if 'project_colors' not in cfg: cfg['project_colors'] = {}
             cfg['project_colors'][p_name] = action['data']['color']
        storage.save_config(cfg)
        
    elif action['type'] == 'add':
        # Undo add = delete
        todos = storage.load_todos()
        todos = [t for t in todos if t.id != action['id']]
        storage.save_todos(todos)
        
    elif action['type'] == 'toggle':
        # Undo toggle = toggle back (no new undo record)
        toggle_todo(action['id'], record_undo=False)
        
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