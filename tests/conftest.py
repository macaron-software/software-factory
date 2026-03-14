"""
Pytest configuration and shared fixtures for TMA Auto-Heal tests
Provides common test fixtures and utilities
"""
# Ref: feat-quality
import pytest
import sys
import os

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def mock_agent():
    """Mock agent for testing"""
    return {
        "name": "Karim Diallo",
        "role": "primary",
        "max_retries": 3
    }


@pytest.fixture
def project_setup_context():
    """Standard project-setup context"""
    return {
        "description": "Test automation project",
        "budget": "50k",
        "timeline": "6 months",
        "load": "High",
        "team_size": 5
    }


@pytest.fixture
def short_output_35_chars():
    """Sample short output that triggers TOO_SHORT error"""
    return "Generic French cu. à compléter"


@pytest.fixture
def valid_french_output():
    """Valid French output >= 200 chars"""
    return """
## Phase: PROJECT-SETUP

### Contexte du projet
Ce projet de développement d'application web nécessite une analyse approfondie
des besoins utilisateurs, une évaluation des risques techniques, et une définition
claire des critères de succès.

### Objectifs
1. Définir les exigences fonctionnelles
2. Identifier les contraintes techniques
3. Établir le calendrier de réalisation
4. Allouer les ressources nécessaires

### Livrables attendus
- Spécifications techniques détaillées
- Plan d'architecture système
- Estimation des ressources nécessaires
- Analyse des risques

### Contraintes
- Budget: 50k
- Timeline: 6 mois
- Équipe: 5 développeurs
"""


@pytest.fixture
def adversarial_retry_scenario():
    """Scenario for adversarial retry exhaustion"""
    return {
        "agent": "Karim Diallo",
        "score": 9,
        "max_retries": 3,
        "phase": "project-setup"
    }


@pytest.fixture
def validation_error_scenarios():
    """All validation error scenarios"""
    return {
        "TOO_SHORT": {
            "actual_length": 35,
            "min_length": 200,
            "message": "TOO_SHORT: 35 chars (min 200 for dev)"
        },
        "SLOP": {
            "output": "Generic French cu. à compléter",
            "detected_patterns": ["cu.", "Generic French", "à compléter"]
        },
        "ADVERSARIAL_EXHAUSTED": {
            "agent": "Karim Diallo",
            "score": 9,
            "message": "Agent Karim Diallo exhausted adversarial retries (score: 9/10)"
        }
    }


@pytest.fixture
def workflow_phases():
    """Complete workflow phases configuration"""
    return {
        "ideation": {"minLength": 100, "next": "project-setup"},
        "project-setup": {
            "minLength": 200,
            "language": "fr",
            "next": "development",
            "validation": "strict"
        },
        "development": {"minLength": 500, "next": "testing"},
        "testing": {"minLength": 300, "next": "production"},
        "production": {"minLength": 200, "next": None}
    }


def pytest_configure(config):
    """Pytest configuration hook"""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "regression: Regression tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test items during collection"""
    for item in items:
        # Add markers based on test file
        if "test_builtins" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_phase" in item.nodeid:
            item.add_marker(pytest.mark.integration)
