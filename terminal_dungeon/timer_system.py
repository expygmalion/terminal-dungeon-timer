from abc import ABC, abstractmethod
import time
from .model import Session

class TimerState(ABC):
    @abstractmethod
    def start(self, context, project, task, duration_mins): pass
    
    @abstractmethod
    def pause(self, context): pass
    
    @abstractmethod
    def resume(self, context): pass
    
    @abstractmethod
    def stop(self, context): pass
    
    @abstractmethod
    def tick(self, context): pass

class StoppedState(TimerState):
    def start(self, context, project, task, duration_mins):
        context.project = project
        context.task = task
        context.duration_secs = duration_mins * 60
        context.start_time = time.time()
        context.elapsed_before_pause = 0
        context.transition_to(RunningState())
        
    def pause(self, context): pass
    def resume(self, context): pass
    def stop(self, context): pass
    def tick(self, context): pass

class RunningState(TimerState):
    def start(self, context, project, task, duration_mins): pass
    
    def pause(self, context):
        context.elapsed_before_pause += (time.time() - context.start_time)
        context.transition_to(PausedState())
        
    def resume(self, context): pass
    
    def stop(self, context):
        elapsed = context.elapsed_before_pause + (time.time() - context.start_time)
        context.callbacks['save_session']("terminated", int(elapsed), context)
        context.transition_to(StoppedState())
        
    def tick(self, context):
        now = time.time()
        elapsed = context.elapsed_before_pause + (now - context.start_time)
        remaining = context.duration_secs - elapsed
        
        if now - context.last_blink > 0.5:
            context.show_colon = not context.show_colon
            context.last_blink = now
            
        if remaining <= 0:
            context.callbacks['save_session']("completed", context.duration_secs, context)
            context.transition_to(FinishedState())

class PausedState(TimerState):
    def start(self, context, project, task, duration_mins): pass
    
    def pause(self, context): pass
    
    def resume(self, context):
        context.start_time = time.time()
        context.transition_to(RunningState())
        
    def stop(self, context):
        elapsed = context.elapsed_before_pause
        context.callbacks['save_session']("terminated", int(elapsed), context)
        context.transition_to(StoppedState())
        
    def tick(self, context): pass

class FinishedState(TimerState):
    def start(self, context, project, task, duration_mins):
        # Restart
        context.transition_to(StoppedState())
        context.start(project, task, duration_mins)
        
    def pause(self, context): pass
    def resume(self, context): pass
    
    def stop(self, context):
        context.transition_to(StoppedState())
        
    def tick(self, context): pass

class TimerContext:
    def __init__(self):
        self.state = StoppedState()
        self.project = ""
        self.task = ""
        self.duration_secs = 0
        self.start_time = 0
        self.elapsed_before_pause = 0
        self.last_blink = 0
        self.show_colon = True
        self.callbacks = {} # save_session
    
    def set_callback(self, name, func):
        self.callbacks[name] = func

    def transition_to(self, state):
        self.state = state
        
    def start(self, project, task, duration_mins):
        self.state.start(self, project, task, duration_mins)
        
    def pause(self):
        self.state.pause(self)
        
    def resume(self):
        self.state.resume(self)
        
    def stop(self):
        self.state.stop(self)
        
    def tick(self):
        self.state.tick(self)
    
    @property
    def is_active(self):
        return not isinstance(self.state, StoppedState)
        
    @property
    def state_name(self):
        if isinstance(self.state, RunningState): return 'running'
        if isinstance(self.state, PausedState): return 'paused'
        if isinstance(self.state, FinishedState): return 'finished'
        return 'stopped'
