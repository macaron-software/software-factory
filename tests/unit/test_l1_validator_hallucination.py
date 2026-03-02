"""
Test unitaire — Validation L1: Détection d'hallucination
Ticket: TMA-AUTOHEAL-001
Comportement attendu: Toute hallucination détectée = reject immédiat (score < 10)
"""
import pytest
from enum import Enum


class ViolationType(Enum):
    """Types de violations L1 — gravité"""
    HALLUCINATION = 1.0  # Pondération maximale: 1.0 = reject immédiat
    SLOP = 0.5
    ECHO = 0.3
    INCOMPLETE = 0.2


class ValidationResult:
    def __init__(self, violations: list[ViolationType]):
        self.violations = violations
        self.score = self._calculate_score()
    
    def _calculate_score(self) -> float:
        """Calcule le score: 1.0 - sum(violations). Hallucination = reject immédiat."""
        penalty = sum(v.violation for v in self.violations)
        return round(1.0 - penalty, 2)
    
    def should_reject(self) -> bool:
        """Reject si score < 10 (soit < 1.0 dans l'échelle 0-1)"""
        return self.score < 1.0


class L1Validator:
    """Validateur L1 — corrige le bug: hallucination doit être fatale"""
    
    def validate(self, agent_output: str, task_type: str) -> ValidationResult:
        violations = []
        
        # Détection d'hallucination (simplifié pour le test)
        # Règle: Si output contient des entités inventées (Comité Stratégique, etc.)
        if "comité stratégique" in agent_output.lower() and task_type == "routage_incident":
            violations.append(ViolationType.HALLUCINATION)
        
        # Autres détections...
        
        return ValidationResult(violations)


# ============================================
# TESTS TDD — Étape 1: Tests qui ÉCHOUENT
# ============================================

def test_hallucination_detected_rejects_immediately():
    """
    [ROUGE] Test attendu: FAIL avant fix
    
    Contexte: Agent output contient "Comité Stratégique" inventé
    Tâche réelle: routage_incident
    Comportement actuel (BUG): Score 9/10 → ACCEPTED
    Comportement attendu: Score < 10 → REJECTED
    """
    validator = L1Validator()
    output_hallucinated = """
    Je vais escalader ce problème au Comité Stratégique pour décision.
    Cette revue de projet nécessite une approbation au niveau exécutif.
    """
    
    result = validator.validate(output_hallucinated, "routage_incident")
    
    # Devrait être REJECT (score < 1.0)
    assert result.should_reject() == True, \
        f"BUG: Hallucination détectée mais score={result.score}/10 → ACCEPTED (attendu: REJECT)"
    assert result.score < 1.0, \
        f"BUG: Score {result.score} ne devrait pas合格 (hallucination = reject immédiat)"


def test_valid_output_accepted():
    """
    [VERT] Test attendu: PASS après fix
    
    Contexte: Output valide, pas d'hallucination
    Comportement attendu: ACCEPTED
    """
    validator = L1Validator()
    output_valid = """
    Incident routé vers l'équipe N2. 
    Ticket créé: INC-2024-00123.
    Priorité: Haute.
    """
    
    result = validator.validate(output_valid, "routage_incident")
    
    # Devrait être ACCEPT (score = 1.0)
    assert result.should_reject() == False
    assert result.score == 1.0


def test_hallucination_weight_is_fatal():
    """
    [ROUGE] Test attendu: FAIL — La pondération de HALLUCINATION doit être 1.0
    """
    hallucination = ViolationType.HALLUCINATION
    
    # HALLUCINATION doit avoir une pondération de 1.0 (reject immédiat)
    assert hallucination.violation == 1.0, \
        f"BUG: HALLUCINATION weight={hallucination.violation} (devrait être 1.0 pour reject immédiat)"


# ============================================
# POINT D'ENTRÉE TEST
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])