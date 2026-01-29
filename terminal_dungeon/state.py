from .timer_system import TimerContext

# --- Global State ---
# Replaces the old SESSION dict
TIMER = TimerContext()

# Legacy placeholder to prevent immediate crashes if I missed a spot, 
# but we aim to remove it.
# SESSION = {} 

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
