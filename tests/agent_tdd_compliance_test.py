#!/usr/bin/env python3
"""
Test de conformité TDD pour les agents.

Ce test vérifie qu'un agent exécutant une tâche TDD
produit effectivement:
1. Un fichier de test
2. Une implémentation
3. Une validation

RED: Ce test échoue actuellement car l'agent ne produit pas ces artefacts.
"""

import pytest
import os
from pathlib import Path


class TestAgentTDDCompliance:
    """Vérifie la conformité du workflow TDD agent."""

    def test_agent_produces_test_file(self):
        """L'agent doit produire un fichier de test."""
        # Chercher les fichiers de test existants
        current_dir = Path(".")
        test_files = list(current_dir.glob("tests/test_*.py"))
        test_files.extend(list(current_dir.glob("test_*.py")))
        
        assert len(test_files) > 0, (
            "FAIL: L'agent n'a produit aucun fichier de test. "
            "Comportement attendu: créer un test avant l'implémentation."
        )

    def test_agent_produces_implementation(self):
        """L'agent doit produire une implémentation."""
        # Vérifier qu'il y a du code dans le projet
        src_dir = Path(".")
        
        py_files = list(src_dir.glob("agents/*.py"))
        assert len(py_files) > 0, (
            "FAIL: L'agent n'a produit aucune implémentation."
        )

    def test_agent_completes_full_workflow(self):
        """Vérifie que les 3 étapes TDD sont complétées."""
        # Ce test échoue explicitement pour le cas diagnosed
        # L'agent s'est arrêté au listing des fichiers
        pytest.fail(
            "FAIL: L'agent s'est arrêté au listing des fichiers. "
            "Le workflow TDD n'a pas été complété. "
            "étape actuelle: FILE_LISTING_ONLY"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])