import yaml
import os
import math
from datetime import datetime

class DustDatabase:
    def __init__(self, db_path: str):
        base, _ = os.path.splitext(db_path)
        self.db_path = base + ".yaml"
        self._clusters = []
        self._load()
        
    def _load(self):
        if not os.path.exists(self.db_path):
            self._clusters = []
            return
            
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if not data:
                    self._clusters = []
                elif isinstance(data, list):
                    valid_clusters = []
                    for item in data:
                        if isinstance(item, dict) and "x" in item and "y" in item:
                            if "observations" in item and isinstance(item["observations"], list):
                                valid_clusters.append(item)
                            else:
                                # Old flat spot format
                                valid_clusters.append({
                                    "id": len(valid_clusters) + 1,
                                    "x": float(item["x"]),
                                    "y": float(item["y"]),
                                    "observations": [{
                                        "image_path": item.get("image_path", ""),
                                        "score": float(item.get("score", 0.7)),
                                        "timestamp": item.get("timestamp", datetime.now().isoformat())
                                    }]
                                })
                    self._clusters = valid_clusters
                elif isinstance(data, dict) and "clusters" in data:
                    self._clusters = data["clusters"]
                else:
                    self._clusters = []
        except Exception as e:
            print(f"[DustDatabase] Load warning: {e}")
            self._clusters = []
            
    def save(self):
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._clusters, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"[DustDatabase] Warning: Could not save database: {e}")

    def _normalize_image_key(self, path: str) -> str:
        return os.path.normpath(path).lower() if path else ""

    def _add_to_clusters(self, x: float, y: float, image_path: str, tolerance: float, score: float = 0.0, timestamp: str = None):
        norm_key = self._normalize_image_key(image_path)
        ts = timestamp or datetime.now().isoformat()
        
        best_cluster = None
        min_dist = float("inf")
        
        for c in self._clusters:
            dist = math.hypot(c["x"] - x, c["y"] - y)
            if dist < tolerance and dist < min_dist:
                min_dist = dist
                best_cluster = c
                
        obs_entry = {
            "image_path": image_path,
            "score": round(score, 3),
            "timestamp": ts
        }
        
        if best_cluster is not None:
            if "observations" not in best_cluster or not isinstance(best_cluster["observations"], list):
                best_cluster["observations"] = []
                
            # Check unique images in cluster
            unique_imgs = {self._normalize_image_key(obs.get("image_path", "")) for obs in best_cluster["observations"] if isinstance(obs, dict)}
            is_new_image = norm_key not in unique_imgs if norm_key else True
            
            # Recalculate cluster center with gentle update
            count = len(best_cluster["observations"])
            best_cluster["x"] = round((best_cluster.get("x", x) * count + x) / (count + 1), 4)
            best_cluster["y"] = round((best_cluster.get("y", y) * count + y) / (count + 1), 4)
            best_cluster["observations"].append(obs_entry)
            
            seen_count = len(unique_imgs) + (1 if is_new_image else 0)
            persistent = seen_count >= 2
            return persistent, seen_count
        else:
            new_id = len(self._clusters) + 1
            new_cluster = {
                "id": new_id,
                "x": round(x, 4),
                "y": round(y, 4),
                "observations": [obs_entry]
            }
            self._clusters.append(new_cluster)
            return False, 1
            
    def check_and_add(self, x: float, y: float, image_path: str, tolerance: float, score: float = 0.0):
        persistent, seen_count = self._add_to_clusters(x, y, image_path, tolerance, score=score)
        self.save()
        return persistent, seen_count
