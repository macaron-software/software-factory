"""
Test fixtures for project-setup phase validation
Simulates the ideation-to-prod workflow configuration
"""

PROJECT_SETUP_FIXTURE = {
    "id": "project-setup",
    "name": "Configuration Projet",
    "description": "Project setup phase defining technical architecture",
    "minLength": 200,
    "language": "fr",
    "next": "development",
    "validation": {
        "type": "strict",
        "required": True,
        "checks": [
            {"min_length": 200},
            {"no_placeholder": True},
            {"has_technical_details": True}
        ]
    },
    "retry": {
        "maxAttempts": 3,
        "strategy": "adversarial",
        "scoreThreshold": 9
    },
    "agents": {
        "primary": "Karim Diallo",
        "fallback": "system"
    }
}

IDEATION_TO_PROD_PHASES = [
    {"id": "ideation", "minLength": 100, "next": "project-setup"},
    PROJECT_SETUP_FIXTURE,
    {"id": "development", "minLength": 500, "next": "testing"},
    {"id": "testing", "minLength": 300, "next": "production"},
    {"id": "production", "minLength": 200, "next": None}
]

ERROR_MESSAGES = {
    "TOO_SHORT": "Output too short: {actual} chars (min {required} for {environment})",
    "SLOP": "Output contains generic placeholder text",
    "ADVERSARIAL_EXHAUSTED": "Agent {agent} exhausted adversarial retries (score: {score}/10)"
}

# Test scenarios
TOO_SHORT_ERROR_SCENARIO = {
    "error_type": "TOO_SHORT",
    "actual_length": 35,
    "min_length": 200,
    "message": "Output too short: 35 chars (min 200 for dev)"
}

SLOP_ERROR_SCENARIO = {
    "error_type": "SLOP",
    "output_contains": "cu",
    "placeholder": "Generic French output with cu."
}

ADVERSARIAL_EXHAUSTED_SCENARIO = {
    "agent": "Karim Diallo",
    "score": 9,
    "max_score": 10,
    "message": "Agent Karim Diallo exhausted adversarial retries (score: 9/10)"
}
