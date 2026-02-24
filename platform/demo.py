"""Demo mode: seed sample data for exploring the platform without LLM keys."""
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DEMO_PROJECTS = [
    {"id": "demo-ecommerce", "name": "E-Commerce Platform", "description": "Full-stack e-commerce with payments, inventory, and analytics", "stack": "python,fastapi,react,postgresql"},
    {"id": "demo-mobile", "name": "Mobile Banking App", "description": "iOS/Android banking app with biometric auth and real-time transactions", "stack": "kotlin,swift,grpc,redis"},
    {"id": "demo-saas", "name": "SaaS Dashboard", "description": "Multi-tenant SaaS analytics dashboard with real-time streaming", "stack": "typescript,nextjs,prisma,kafka"},
    {"id": "demo-payflow", "name": "PayFlow — Payment Orchestration", "description": "Multi-PSP routing, 3DS2 auth, reconciliation, real-time fraud scoring", "stack": "go,typescript,react,postgresql"},
    {"id": "demo-dataforge", "name": "DataForge — Data Pipeline", "description": "Enterprise data pipeline with ingestion, transformation, quality checks, lineage tracking", "stack": "python,rust,typescript,kafka"},
    {"id": "demo-urbanpulse", "name": "UrbanPulse — Smart City", "description": "Real-time traffic flow, public transport optimization, fleet management, air quality", "stack": "rust,svelte,python,timescaledb"},
]

DEMO_MISSIONS = [
    {"name": "Payment Gateway Integration", "project_id": "demo-ecommerce", "type": "epic", "status": "active", "priority": "high"},
    {"name": "User Authentication Redesign", "project_id": "demo-ecommerce", "type": "feature", "status": "completed", "priority": "critical"},
    {"name": "Mobile Push Notifications", "project_id": "demo-mobile", "type": "epic", "status": "active", "priority": "medium"},
    {"name": "Biometric Login Flow", "project_id": "demo-mobile", "type": "feature", "status": "in_review", "priority": "high"},
    {"name": "Real-time Analytics Pipeline", "project_id": "demo-saas", "type": "epic", "status": "planning", "priority": "high"},
    {"name": "Tenant Isolation Security Audit", "project_id": "demo-saas", "type": "security", "status": "active", "priority": "critical"},
    {"name": "TMA - Production Monitoring", "project_id": "demo-ecommerce", "type": "program", "status": "active", "priority": "medium"},
    {"name": "Technical Debt Reduction Q1", "project_id": "demo-saas", "type": "debt", "status": "planning", "priority": "low"},
    # PayFlow missions
    {"name": "TMA — PayFlow", "project_id": "demo-payflow", "type": "program", "status": "active", "priority": "high"},
    {"name": "Sécurité — PayFlow", "project_id": "demo-payflow", "type": "security", "status": "active", "priority": "critical"},
    {"name": "Dette Technique — PayFlow", "project_id": "demo-payflow", "type": "debt", "status": "planning", "priority": "medium"},
    {"name": "Self-Healing — PayFlow", "project_id": "demo-payflow", "type": "program", "status": "active", "priority": "high"},
    # DataForge missions
    {"name": "TMA — DataForge", "project_id": "demo-dataforge", "type": "program", "status": "active", "priority": "high"},
    {"name": "Sécurité — DataForge", "project_id": "demo-dataforge", "type": "security", "status": "active", "priority": "critical"},
    {"name": "Dette Technique — DataForge", "project_id": "demo-dataforge", "type": "debt", "status": "planning", "priority": "medium"},
    {"name": "Self-Healing — DataForge", "project_id": "demo-dataforge", "type": "program", "status": "active", "priority": "high"},
    # UrbanPulse missions
    {"name": "TMA — UrbanPulse", "project_id": "demo-urbanpulse", "type": "program", "status": "active", "priority": "high"},
    {"name": "Sécurité — UrbanPulse", "project_id": "demo-urbanpulse", "type": "security", "status": "active", "priority": "critical"},
    {"name": "Dette Technique — UrbanPulse", "project_id": "demo-urbanpulse", "type": "debt", "status": "planning", "priority": "medium"},
    {"name": "Self-Healing — UrbanPulse", "project_id": "demo-urbanpulse", "type": "program", "status": "active", "priority": "high"},
]


def is_demo_mode() -> bool:
    return os.environ.get("PLATFORM_LLM_PROVIDER", "").lower() == "demo"


def seed_demo_data():
    """Seed sample projects, missions, and incidents for demo mode."""
    if not is_demo_mode():
        return
    from .db.migrations import get_db
    db = get_db()
    cur = db.cursor()

    # Check if demo data already exists
    cur.execute("SELECT COUNT(*) FROM projects WHERE id LIKE 'demo-%'")
    if cur.fetchone()[0] > 0:
        logger.info("Demo data already seeded, skipping")
        return

    now = datetime.utcnow().isoformat()

    # Seed projects
    for p in DEMO_PROJECTS:
        cur.execute(
            "INSERT OR IGNORE INTO projects (id, name, description, status, created_at) VALUES (?, ?, ?, 'active', ?)",
            (p["id"], p["name"], p["description"], now),
        )

    # Seed missions
    for i, m in enumerate(DEMO_MISSIONS):
        mid = f"demo-mission-{i+1:03d}"
        created = (datetime.utcnow() - timedelta(days=30 - i * 3)).isoformat()
        cur.execute(
            "INSERT OR IGNORE INTO missions (id, name, project_id, type, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, m["name"], m["project_id"], m["type"], m["status"], created),
        )

    # Seed a few incidents
    incidents = [
        ("High memory usage on payment service", "P2", "resource_exhaustion"),
        ("Intermittent 502 on checkout API", "P1", "http_error"),
        ("Slow query on analytics dashboard", "P3", "performance"),
    ]
    for j, (title, severity, error_type) in enumerate(incidents):
        iid = f"demo-incident-{j+1:03d}"
        cur.execute(
            "INSERT OR IGNORE INTO platform_incidents (id, title, severity, error_type, status, created_at) VALUES (?, ?, ?, ?, 'open', ?)",
            (iid, title, severity, error_type, now),
        )

    db.commit()
    logger.info("Demo data seeded: %d projects, %d missions, %d incidents",
                len(DEMO_PROJECTS), len(DEMO_MISSIONS), len(incidents))
