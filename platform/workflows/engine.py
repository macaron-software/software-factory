"""
Workflow Engine Module
=======================

Executes multi-phase workflows with proper error handling.

Target Error: TOO_SHORT (35 chars vs min 200 for dev)
"""
# Ref: feat-workflows

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from ..errors.phase_errors import PhaseError
from ..validation import InputValidator
from ..agents.tool_runner import run_pattern


class PhaseStatus(Enum):
    """Status of a phase execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseResult:
    """Result of phase execution."""
    phase: str
    status: PhaseStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[PhaseError] = None


class WorkflowEngine:
    """
    Engine for executing multi-phase workflows.
    
    Handles phase transitions, validation, and error management.
    """
    
    # Default phase sequence
    DEFAULT_PHASES = [
        "project-setup",
        "ideation",
        "validation"
    ]
    
    def __init__(self, phases: Optional[List[str]] = None):
        """
        Initialize workflow engine.
        
        Args:
            phases: Optional custom phase sequence
        """
        self.phases = phases or self.DEFAULT_PHASES.copy()
        self.current_phase_index = 0
        self.results: List[PhaseResult] = []
    
    def execute(
        self,
        input_data: str,
        mode: str = "dev",
        start_phase: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the workflow.
        
        Args:
            input_data: Initial input data
            mode: Execution mode (dev/prod)
            start_phase: Optional phase to start from
            
        Returns:
            Workflow execution result
        """
        # Determine starting phase
        if start_phase:
            try:
                self.current_phase_index = self.phases.index(start_phase)
            except ValueError:
                return {
                    "status": "error",
                    "error": f"Phase '{start_phase}' not found in workflow",
                    "completed_phases": []
                }
        
        # Execute phases sequentially
        for phase in self.phases[self.current_phase_index:]:
            result = self.execute_phase(phase, input_data, mode)
            self.results.append(result)
            
            if result.status == PhaseStatus.FAILED:
                return {
                    "status": "failed",
                    "failed_phase": phase,
                    "error": result.error.to_dict() if result.error else None,
                    "completed_phases": [r.phase for r in self.results[:-1]]
                }
            
            # Use output as input for next phase
            if result.data:
                input_data = result.data.get("output", input_data)
        
        return {
            "status": "success",
            "phases": [r.phase for r in self.results],
            "final_data": self.results[-1].data if self.results else None
        }
    
    def execute_phase(
        self,
        phase: str,
        input_data: str,
        mode: str = "dev"
    ) -> PhaseResult:
        """
        Execute a single phase.
        
        Args:
            phase: Phase name
            input_data: Input data for phase
            mode: Execution mode
            
        Returns:
            PhaseResult
        """
        try:
            # Validate input for project-setup phase
            if phase == "project-setup":
                validation_result = InputValidator.validate_input_length(
                    input_data, mode, phase
                )
                
                if not validation_result.is_valid:
                    error = validation_result.error
                    return PhaseResult(
                        phase=phase,
                        status=PhaseStatus.FAILED,
                        error=error
                    )
            
            # Execute pattern
            execution_result = run_pattern(phase, input_data, mode)
            
            if execution_result.status.value == "success":
                return PhaseResult(
                    phase=phase,
                    status=PhaseStatus.SUCCESS,
                    data=execution_result.data
                )
            else:
                return PhaseResult(
                    phase=phase,
                    status=PhaseStatus.FAILED,
                    error=execution_result.error
                )
                
        except PhaseError as e:
            return PhaseResult(
                phase=phase,
                status=PhaseStatus.FAILED,
                error=e
            )
        except Exception as e:
            return PhaseResult(
                phase=phase,
                status=PhaseStatus.FAILED,
                error=PhaseError(
                    error_type=PhaseError.VALIDATION_FAILED,
                    phase=phase,
                    message=str(e)
                )
            )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current workflow status.
        
        Returns:
            Status dictionary
        """
        return {
            "phases": self.phases,
            "current_phase": self.phases[self.current_phase_index] if self.current_phase_index < len(self.phases) else None,
            "completed_phases": [r.phase for r in self.results],
            "results": [r.status.value for r in self.results]
        }


# Module-level convenience function
def execute_workflow(
    input_data: str,
    mode: str = "dev",
    phases: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Execute a workflow with default settings.
    
    Args:
        input_data: Initial input
        mode: Execution mode
        phases: Optional custom phases
        
    Returns:
        Workflow result
    """
    engine = WorkflowEngine(phases)
    return engine.execute(input_data, mode)
