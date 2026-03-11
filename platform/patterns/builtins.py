"""
Pattern Builtins Module
========================

Built-in patterns for the phase workflow system.

Target Error: TOO_SHORT (35 chars vs min 200 for dev)
"""

from typing import Dict, Any, Optional
from ..errors.phase_errors import PhaseError
from ..validation import InputValidator


class BasePattern:
    """Base class for all patterns."""
    
    name: str = "base"
    description: str = "Base pattern"
    
    def execute(
        self,
        input_data: str,
        mode: str = "dev",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the pattern.
        
        Args:
            input_data: Input data for pattern
            mode: Execution mode (dev/prod)
            context: Optional execution context
            
        Returns:
            Execution result dictionary
        """
        raise NotImplementedError("Subclasses must implement execute()")


class ProjectSetupPattern(BasePattern):
    """
    Project Setup Pattern
    
    Initializes a new project with the given description.
    
    Length requirements:
    - dev mode: min 200 chars
    - prod mode: min 50 chars
    """
    
    name = "project-setup"
    description = "Initialize a new project"
    
    def execute(
        self,
        input_data: str,
        mode: str = "dev",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute project-setup pattern.
        
        Args:
            input_data: Project description (must meet min length)
            mode: Execution mode
            context: Optional context
            
        Returns:
            Result dictionary with status and data
            
        Raises:
            PhaseError: If input validation fails
        """
        context = context or {}
        
        # Validate input length
        validation_result = InputValidator.validate_input_length(
            input_data, mode, self.name
        )
        
        if not validation_result.is_valid:
            raise validation_result.error
        
        # Execute project setup
        return {
            "status": "success",
            "phase": self.name,
            "mode": mode,
            "project_id": self._generate_project_id(input_data),
            "next_phase": "ideation",
            "language": "fr",  # Default French output
            "message": "Projet initialisé avec succès."
        }
    
    def _generate_project_id(self, input_data: str) -> str:
        """Generate project ID from input."""
        import hashlib
        hash_obj = hashlib.md5(input_data.encode())
        return f"PRJ-{hash_obj.hexdigest()[:8].upper()}"


class IdeationPattern(BasePattern):
    """Ideation phase pattern."""
    
    name = "ideation"
    description = "Brainstorm and generate ideas"
    
    def execute(
        self,
        input_data: str,
        mode: str = "dev",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute ideation pattern."""
        return {
            "status": "success",
            "phase": self.name,
            "mode": mode,
            "ideas": [],
            "next_phase": "validation",
            "language": "fr"
        }


class ValidationPattern(BasePattern):
    """Validation phase pattern."""
    
    name = "validation"
    description = "Validate project requirements"
    
    def execute(
        self,
        input_data: str,
        mode: str = "dev",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute validation pattern."""
        return {
            "status": "success",
            "phase": self.name,
            "mode": mode,
            "validations": [],
            "next_phase": None,
            "language": "fr"
        }


# Registry of available patterns
_PATTERNS = {
    "project-setup": ProjectSetupPattern(),
    "ideation": IdeationPattern(),
    "validation": ValidationPattern(),
}


def get_pattern(pattern_name: str) -> Optional[BasePattern]:
    """
    Get a pattern by name.
    
    Args:
        pattern_name: Name of the pattern
        
    Returns:
        Pattern instance or None if not found
    """
    return _PATTERNS.get(pattern_name)


def list_patterns() -> Dict[str, str]:
    """
    List all available patterns.
    
    Returns:
        Dictionary of pattern names to descriptions
    """
    return {name: pattern.description for name, pattern in _PATTERNS.items()}
