from abc import ABC, abstractmethod
from ..models import DetectorResult
import numpy as np

class BaseDetector(ABC):
    def __init__(self, config):
        self.config = config
        
    @abstractmethod
    def analyze(self, original_img: np.ndarray, analysis_img: np.ndarray, context: dict) -> DetectorResult:
        pass
