import json
import os
from .config import DATA_FILE, TODO_FILE, CONFIG_FILE, DEFAULT_CONFIG
from .model import Task, Session

# --- Data Management ---
def load_todos():
    if not os.path.exists(TODO_FILE): return []
    try:
        with open(TODO_FILE, 'r') as f: 
            data = json.load(f)
            return [Task.from_dict(d) for d in data]
    except: return []

def save_todos(todos):
    data = [t.to_dict() if hasattr(t, 'to_dict') else t for t in todos]
    with open(TODO_FILE, 'w') as f: json.dump(data, f, indent=2)

def load_history():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: 
            data = json.load(f)
            return [Session.from_dict(d) for d in data]
    except: return []

def save_history(history):
    data = [h.to_dict() if hasattr(h, 'to_dict') else h for h in history]
    with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=2)

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
