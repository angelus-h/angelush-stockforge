from dataclasses import dataclass

@dataclass
class QualityConfig:
    mode: str = "paranoid"
    
    dust_sensitivity: float = 0.8  
    dust_persistence_tolerance: float = 0.02 
    
    # Sharpness parameters
    sharpness_global_threshold: float = 50.0
    sharpness_local_anomaly_ratio: float = 0.2
    
    # Exposure parameters
    shadow_clipping_threshold_percent: float = 1.0
    highlight_clipping_threshold_percent: float = 1.0
    
    # Dead pixel parameters (increased threshold to avoid false positives on high frequency textures like fields/flowers)
    dead_pixel_threshold: int = 250
    
    # Image analysis resolution
    analysis_resolution_max_dim: int = 2048 

