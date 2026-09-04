import yaml
import os
from datetime import datetime

class DustDatabase:
    def __init__(self, db_path: str):
        # Always enforce .yaml extension if they pass .sqlite or .json
        base, _ = os.path.splitext(db_path)
        self.db_path = base + ".yaml"
        self._spots = []
        self._load()
        
    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = yaml.safe_load(f)
                    self._spots = data if data else []
            except Exception:
                self._spots = []
        else:
            self._spots = []
            
    def save(self):
        with open(self.db_path, 'w') as f:
            yaml.dump(self._spots, f, default_flow_style=False, sort_keys=False)
            
    def check_and_add(self, x: float, y: float, image_path: str, tolerance: float) -> bool:
        persistent = False
        
        # Check if a similar spot already exists
        for spot in self._spots:
            if abs(spot['x'] - x) < tolerance and abs(spot['y'] - y) < tolerance:
                persistent = True
                break
                
        # Add new observation
        self._spots.append({
            "x": round(x, 4),
            "y": round(y, 4),
            "image_path": image_path,
            "timestamp": datetime.now().isoformat()
        })
        
        # Save after every addition to keep it updated, or this could be optimized later
        self.save()
        
        return persistent
