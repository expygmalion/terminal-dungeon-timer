from datetime import datetime, timedelta
from . import storage

def get_project_tags(project_name):
    # 1. Config Tags (Base)
    cfg = storage.load_config()
    config_tags = cfg.get('project_tags', {}).get(project_name, [])
    
    # Map tag -> last_seen_timestamp
    # Config tags get a low priority timestamp (e.g. empty string)
    tag_recency = {t: "" for t in config_tags}
    
    # 2. Todo Tags (Usage)
    todos = storage.load_todos()
    for t in todos:
        if t.get('project') == project_name:
            ts = t.get('timestamp', "")
            for tag in t.get('tags', []):
                # Update if this usage is more recent
                if tag not in tag_recency or ts > tag_recency[tag]:
                    tag_recency[tag] = ts
                    
    # 3. Sort by recency descending
    # Tags with same timestamp (e.g. config only) will be sorted by name via tuple comparison if we want deterministic
    # But python sort is stable. Let's sort by key=timestamp desc
    sorted_tags = sorted(tag_recency.keys(), key=lambda x: tag_recency[x], reverse=True)
    
    return sorted_tags

def get_unique_projects():
    todos = storage.load_todos()
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
    history = storage.load_history()
    return sorted(list(set(i['task'] for i in history if i.get('project') == project_name and i.get('task'))))

def get_all_used_tags():
    todos = storage.load_todos()
    tags = set()
    for t in todos:
        for tag in t.get('tags', []):
            tags.add(tag)
    return sorted(list(tags))

def determine_class(project_name, config):
    # 1. Check direct project tags
    tags = config['project_tags'].get(project_name, [])
    
    # 2. Add words from project name as implicit tags
    if project_name:
        tags.extend(project_name.lower().replace("-", " ").split())
    
    # 3. Match against classes
    best_match = "Novice"
    max_matches = 0
    
    for cls in config['classes']:
        matches = sum(1 for t in cls['tags'] if any(pt in t or t in pt for pt in tags))
        if matches > max_matches:
            max_matches = matches
            best_match = cls['name']
            
    if max_matches == 0 and project_name:
        return f"{project_name} Mancer"
    
    return best_match

def format_duration(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def parse_time_str(s):
    try:
        parts = s.split(':')
        if len(parts) == 3: return int(parts[0])*60 + int(parts[1]) + int(parts[2])/60
        if len(parts) == 2: return int(parts[0]) + int(parts[1])/60
        if len(parts) == 1: return float(parts[0])
    except: pass
    return None

def is_subsequence(q, t):
    it = iter(t.lower()); q = q.lower().replace(" ", "")
    return all(c in it for c in q)

def clean_tags(tags):
    if not tags: return []
    return sorted(list(set(t.strip().upper() for t in tags if t and t.strip())))

def calculate_stats(history):
    today = datetime.now().date()
    yest = today - timedelta(days=1)
    tt = 0
    ty = 0
    for i in history:
        try:
            d = datetime.fromisoformat(i['timestamp']).date()
            dur = i['duration_minutes'] if i.get('status')=='completed' else (i.get('actual_duration_seconds',0)/60)
            if d == today: tt += dur
            elif d == yest: ty += dur
        except: pass
    return tt, ty, (tt/ty if ty else (float('inf') if tt else 0))
