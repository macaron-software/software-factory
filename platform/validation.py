"""
Input Validation Module
=======================

Validation utilities for phase inputs in the project-setup pattern.

Target Error: TOO_SHORT (35 chars vs min 200 for dev)
"""

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from .errors.phase_errors import PhaseError


@dataclass
class ValidationResult:
    """Result of input validation."""
    is_valid: bool
    error: Optional[PhaseError] = None
    current_length: int = 0
    min_length: int = 0
    max_length: int = 0


class InputValidator:
    """
    Validator for phase inputs with length constraints.
    
    Length requirements:
    - dev mode: min 200 chars
    - prod mode: min 50 chars
    """
    
    # Mode-specific minimum lengths
    MIN_LENGTH_DEV = 200
    MIN_LENGTH_PROD = 50
    MAX_LENGTH = 10000
    
    @classmethod
    def validate_input_length(
        cls,
        input_data: str,
        mode: str = "dev",
        phase: str = "project-setup"
    ) -> ValidationResult:
        """
        Validate input length based on mode.
        
        Args:
            input_data: The input string to validate
            mode: Execution mode ('dev' or 'prod')
            phase: Phase name for error context
            
        Returns:
            ValidationResult with validation status and error details
        """
        if not input_data:
            return ValidationResult(
                is_valid=False,
                error=PhaseError(
                    error_type=PhaseError.TOO_SHORT,
                    current_length=0,
                    min_length=cls.MIN_LENGTH_DEV if mode == "dev" else cls.MIN_LENGTH_PROD,
                    phase=phase,
                    message="L'entrée ne peut pas être vide."
                ),
                current_length=0,
                min_length=cls.MIN_LENGTH_DEV if mode == "dev" else cls.MIN_LENGTH_PROD
            )
        
        current_length = len(input_data)
        
        # Determine minimum based on mode
        min_length = cls.MIN_LENGTH_DEV if mode == "dev" else cls.MIN_LENGTH_PROD
        
        # Check minimum length
        if current_length < min_length:
            return ValidationResult(
                is_valid=False,
                error=PhaseError(
                    error_type=PhaseError.TOO_SHORT,
                    current_length=current_length,
                    min_length=min_length,
                    phase=phase
                ),
                current_length=current_length,
                min_length=min_length,
                max_length=cls.MAX_LENGTH
            )
        
        # Check maximum length
        if current_length > cls.MAX_LENGTH:
            return ValidationResult(
                is_valid=False,
                error=PhaseError(
                    error_type=PhaseError.TOO_LONG,
                    current_length=current_length,
                    max_length=cls.MAX_LENGTH,
                    phase=phase
                ),
                current_length=current_length,
                min_length=min_length,
                max_length=cls.MAX_LENGTH
            )
        
        # Valid input
        return ValidationResult(
            is_valid=True,
            current_length=current_length,
            min_length=min_length,
            max_length=cls.MAX_LENGTH
        )
    
    @classmethod
    def validate_project_setup_input(
        cls,
        input_data: str,
        mode: str = "dev"
    ) -> Tuple[bool, Optional[PhaseError]]:
        """
        Convenience method for project-setup validation.
        
        Args:
            input_data: Input to validate
            mode: Execution mode
            
        Returns:
            Tuple of (is_valid, error)
        """
        result = cls.validate_input_length(input_data, mode, "project-setup")
        return result.is_valid, result.error
    
    @classmethod
    def get_min_length_for_mode(cls, mode: str) -> int:
        """
        Get minimum length requirement for a given mode.
        
        Args:
            mode: Execution mode
            
        Returns:
            Minimum length in characters
        """
        return cls.MIN_LENGTH_DEV if mode == "dev" else cls.MIN_LENGTH_PROD


def validate_input_length(input_data: str, mode: str = "dev") -> ValidationResult:
    """
    Module-level function for input validation.
    
    Args:
        input_data: Input string to validate
        mode: Execution mode ('dev' or 'prod')
        
    Returns:
        ValidationResult
    """
    return InputValidator.validate_input_length(input_data, mode)
