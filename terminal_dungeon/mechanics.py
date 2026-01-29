from abc import ABC, abstractmethod
from typing import List, Dict

class XPStrategy(ABC):
    @abstractmethod
    def calculate_xp(self, duration_mins: float) -> int: pass

class StandardXPStrategy(XPStrategy):
    def calculate_xp(self, duration_mins: float) -> int:
        return int(duration_mins) # 1 min = 1 XP

class ClassStrategy(ABC):
    @abstractmethod
    def determine_class(self, project_name: str, config: dict) -> str: pass

class KeywordClassStrategy(ClassStrategy):
    def determine_class(self, project_name: str, config: dict) -> str:
        # 1. Check direct project tags
        tags = config['project_tags'].get(project_name, [])
        # Clone to avoid modifying config
        tags = list(tags)
        
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
