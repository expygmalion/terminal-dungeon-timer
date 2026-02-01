from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
import uuid

@dataclass
class Task:
    content: str
    project: str = "General"
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    tags: List[str] = field(default_factory=list)
    status: str = "pending" # pending, done
    description: str = ""
    focused: bool = False
    priority: int = 1 # 1-5
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    last_session_id: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def copy(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data):
        # Filter keys to ensure backward compatibility/robustness
        valid_keys = cls.__annotations__.keys()
        clean_data = {k: v for k, v in data.items() if k in valid_keys}
        # Provide defaults for missing fields if any
        return cls(**clean_data)

    def __getitem__(self, key):
        return getattr(self, key)
    
    def get(self, key, default=None):
        return getattr(self, key, default)
    
    def __setitem__(self, key, value):
        setattr(self, key, value)

@dataclass
class Session:
    project: str
    task: str
    duration_minutes: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "completed" # completed, terminated
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actual_duration_seconds: int = 0
    manual_log: bool = False
    xp_multiplier: float = 1.0
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        valid_keys = cls.__annotations__.keys()
        clean_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**clean_data)

    def __getitem__(self, key):
        return getattr(self, key)
    
    def get(self, key, default=None):
        return getattr(self, key, default)
    
    def __setitem__(self, key, value):
        setattr(self, key, value)
