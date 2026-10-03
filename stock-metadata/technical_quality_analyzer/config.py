from dataclasses import dataclass

@dataclass
class QualityConfig:
    mode: str = "production"  # "production" (high precision) or "paranoid" (high recall)
    
    dust_sensitivity: float = 0.8  
    dust_persistence_tolerance: float = 0.02 
    dust_min_score_production: float = 0.65
    dust_min_score_paranoid: float = 0.45
    
    # Sharpness parameters
    sharpness_global_threshold: float = 50.0
    sharpness_local_anomaly_ratio: float = 0.2
    
    # Exposure parameters
    shadow_clipping_threshold_percent: float = 1.0
    highlight_clipping_threshold_percent: float = 1.0
    
    # Dead pixel parameters (increased threshold to avoid false positives on high frequency textures like fields/flowers)
    dead_pixel_threshold: int = 250
    
    # Noise parameters
    # Fast noise sigma estimation thresholds (Immerkaer method)
    noise_sigma_review_production: float = 8.0
    noise_sigma_high_risk_production: float = 14.0
    noise_sigma_review_paranoid: float = 5.0
    noise_sigma_high_risk_paranoid: float = 10.0
    
    # Chrominance noise thresholds (high frequency std-dev in Lab color space)
    chroma_noise_review_production: float = 4.5
    chroma_noise_high_risk_production: float = 8.0
    chroma_noise_review_paranoid: float = 3.5
    chroma_noise_high_risk_paranoid: float = 6.0
    
    # Image analysis resolution
    analysis_resolution_max_dim: int = 2048 

