{
    "approved": false,
    "issues": [
        {
            "rule": "INCOMPLETE_FILE",
            "severity": "reject",
            "points": 10,
            "message": "Fichier test_webhooks_payload_size.py est tronqué - ligne 120: 'mock_pool_ctx.__aexit__ = AsyncMock()' est coupé, assertions manquantes pour test_payload_at_exact_limit_is_accepted",
            "line": 120,
        },
        {
            "rule": "MISSING_ASSERTIONS",
            "severity": "warning",
            "points": 2,
            "message": "test_payload_at_exact_limit_is_accepted ne vérifie pas que la limite de taille est configurable (via MAX_PAYLOAD_SIZE env var ou paramètre)",
            "line": 105,
        },
        {
            "rule": "NO_TEST_FOR_CONFIGURABLE_LIMIT",
            "severity": "warning",
            "points": 2,
            "message": "Pas de test pour vérifier que la limite de taille peut être modifiée via configuration (la docstring mentionne 'Payload size limit is configurable' mais pas de test)",
            "line": 1,
        },
    ],
    "reasoning": "Code incomplet - fichier tronqué, assertions manquantes. Les mocks et tests existants sont corrects, mais le test final est incomplet.",
}
