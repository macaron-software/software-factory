#!/usr/bin/env python3
"""
Tests unitaires pour la vérification de qualité des outputs agents
Reproduit le defect: L1 SLOP + L1 ECHO sur Rachid Mansouri
"""
import pytest
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_quality_enforcer import QualityEnforcer


class TestAgentQualityVerification:
    """Tests pour vérifier que l'agent fait un travail réel de vérification"""
    
    def setup_method(self):
        """Setup avant chaque test"""
        self.enforcer = QualityEnforcer()
    
    def test_agent_must_not_produce_slop(self):
        """L1 SLOP: Agent ne doit pas produire un output minimal"""
        # Données de test - reproduit l'output SLOP de Rachid Mansouri
        bad_output = "# Diagnostic\n\nFichiers analysés:\n- file1.py\n- file2.py"
        context = {
            "task_title": "Diagnostiquer l'erreur quality_rejection",
            "score": 8.0
        }
        
        is_valid, details = self.enforcer.check_output(bad_output, context)
        
        # Ce test doit FAIL actuellement (RED) car l'output est du SLOP
        assert len(bad_output) >= 200, f"Output trop court: {len(bad_output)} < 200 chars"
        assert details["verification_performed"] == True, "Pas de vérification réelle = SLOP"
    
    def test_agent_must_not_produce_echo(self):
        """L1 ECHO: Agent ne doit pas juste reformuler le titre"""
        task_title = "Diagnostiquer l'erreur quality_rejection"
        
        # Output qui est juste une reformulation
        echo_output = "Diagnostic de l'erreur quality_rejection"
        
        context = {"task_title": task_title, "score": 10.0}
        
        is_valid, details = self.enforcer.check_output(echo_output, context)
        
        # Vérification: le contenu doit avoir une valeur ajoutée
        words_in_task = set(task_title.lower().split())
        words_in_response = set(echo_output.lower().split())
        
        overlap_ratio = len(words_in_task & words_in_response) / len(words_in_task)
        
        # Ce test doit FAIL (RED)
        assert overlap_ratio < 0.6, f"Trop de chevauchement: {overlap_ratio:.2f} >= 0.6 = ECHO"
    
    def test_quality_score_threshold(self):
        """Le score doit atteindre le seuil de 9.0"""
        output = "x" * 300  # Long enough
        context = {
            "task_title": "Tâche test",
            "score": 8.0  # Score actuel problème
        }
        
        is_valid, details = self.enforcer.check_output(output, context)
        
        # Ce test doit FAIL (RED) car score < 9.0
        assert details["score"] >= 9.0, f"Score {details['score']} en dessous du seuil 9.0"
    
    # === EDGE CASES ===
    
    def test_empty_output(self):
        """Edge case: output vide"""
        is_valid, details = self.enforcer.check_output("", {"score": 10.0})
        assert is_valid == False, "Output vide doit être rejeté"
    
    def test_null_task_title(self):
        """Edge case: titre nul"""
        is_valid, details = self.enforcer.check_output(
            "some content here that is long enough", 
            {"task_title": None, "score": 10.0}
        )
        # Ne doit pas crash
        assert details is not None
    
    def test_score_exactly_9_0(self):
        """Edge case: score pile au seuil"""
        output = "x" * 200
        is_valid, details = self.enforcer.check_output(
            output, 
            {"score": 9.0, "task_title": ""}
        )
        assert is_valid == True, "Score exactement 9.0 doit passer"


class TestQualityEnforcer:
    """Tests pour la classe QualityEnforcer"""
    
    def setup_method(self):
        self.enforcer = QualityEnforcer()
    
    def test_enforcer_initialization(self):
        """Test l'initialisation de l'enforcer"""
        assert self.enforcer.MIN_CONTENT_LENGTH == 200
        assert self.enforcer.MAX_ECHO_RATIO == 0.6
        assert self.enforcer.MIN_SCORE == 9.0
    
    def test_check_echo_ratio_calculation(self):
        """Test le calcul du ratio d'echo"""
        # 80% de chevauchement - doit échouer
        task = "diagnostiquer erreur quality rejection"
        output = "diagnostiquer quality rejection"  # 3/4 mots = 75%
        
        is_echo_free = self.enforcer._check_echo(output, task)
        assert is_echo_free == False
    
    def test_enforce_verification_work(self):
        """Test que l'enforcer demande du travail réel"""
        result = self.enforcer.enforce_verification_work(
            "Rachid Mansouri", 
            {"task": "test"}
        )
        
        assert result["agent_id"] == "Rachid Mansouri"
        assert "required_checks" in result
        assert result["min_evidence_points"] == 5