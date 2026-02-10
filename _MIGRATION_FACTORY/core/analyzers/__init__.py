"""
Analyzers - Framework-specific codebase analyzers

Supported:
- Angular (16→17, 17→18)
- React (future)
- Vue (future)
"""

from .angular_analyzer import AngularAnalyzer, AnalysisResult

__all__ = ['AngularAnalyzer', 'AnalysisResult']
