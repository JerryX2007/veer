"""Automatic rally and highlight detection for match footage.

Pure Python + NumPy/OpenCV, no web or database dependencies: `analyze_video`
takes a video path and returns rallies, highlights and a highlight reel (as
timestamps). Run it from the command line with `python -m app.analysis`.
"""

from .config import AnalysisConfig
from .pipeline import AnalysisResult, analyze_video

__all__ = ["AnalysisConfig", "AnalysisResult", "analyze_video"]
