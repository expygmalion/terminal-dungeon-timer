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
