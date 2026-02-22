#!/usr/bin/env python3
"""
Test Skills Injection with Real Mission Scenarios
==================================================

Tests the complete skills injection pipeline with realistic mission contexts
for different agent roles (Product Manager, Tech Lead, QA Lead, etc.)

Usage:
    python3 -m skills_injection.test_real_missions [--verbose]
"""

import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills_injection.agent_enhancer import AgentEnhancer

# =============================================================================
# Test Mission Scenarios
# =============================================================================

TEST_MISSIONS = [
    {
        "role": "Product Manager",
        "mission": """
        We need to implement a multi-factor authentication (MFA) system for our SaaS platform.
        Current state: Basic email/password login exists.
        Goal: Add TOTP-based 2FA with QR code enrollment, backup codes, and remember device option.
        
        Requirements:
        - User-friendly enrollment flow with clear instructions
        - Support for authenticator apps (Google Authenticator, Authy)
        - Generate and display 10 backup codes
        - "Remember this device for 30 days" checkbox
        - Admin can enforce MFA for all users or specific roles
        
        Constraints:
        - Must work on mobile and desktop
        - WCAG 2.1 AA compliance required
        - Max 3 steps in enrollment flow
        """,
        "expected_skills": ["mfa", "authentication", "security", "ux", "wcag", "saas"],
        "expected_count": 5,
    },
    {
        "role": "Tech Lead",
        "mission": """
        Architecture review needed for our microservices backend migration.
        Current: Monolithic PHP application (~200k LOC)
        Target: Event-driven microservices with Python FastAPI
        
        Technical challenges:
        - 15+ database tables with complex relationships
        - Real-time notifications (WebSockets)
        - File uploads and processing (images, PDFs)
        - Background jobs (Celery)
        - Multi-tenant with row-level security
        
        Need to design:
        1. Service boundaries and API contracts
        2. Event bus architecture (Kafka? RabbitMQ?)
        3. Database migration strategy
        4. Deployment pipeline (Docker, K8s)
        5. Observability stack (logs, metrics, traces)
        """,
        "expected_skills": [
            "microservices",
            "architecture",
            "fastapi",
            "kafka",
            "kubernetes",
            "migration",
        ],
        "expected_count": 8,
    },
    {
        "role": "QA Lead",
        "mission": """
        Set up comprehensive E2E testing for critical user flows.
        Application: Multi-tenant SaaS with role-based access (Owner, Admin, Teacher, Student)
        
        Flows to test:
        1. User registration and email verification
        2. Login with MFA (TOTP)
        3. Dashboard with real-time updates
        4. Create/edit/delete resources (CRUD)
        5. File upload with progress bar
        6. Export data (CSV, PDF)
        7. Permissions and access control
        
        Requirements:
        - Playwright or Cypress
        - Run tests in CI/CD (GitHub Actions)
        - Test data isolation per test
        - Screenshot on failure
        - Coverage report
        - Cross-browser testing (Chrome, Firefox, Safari)
        """,
        "expected_skills": ["e2e", "playwright", "testing", "ci-cd", "permissions"],
        "expected_count": 6,
    },
    {
        "role": "Data Engineer",
        "mission": """
        Build data pipeline for analytics dashboard.
        
        Sources:
        - Production PostgreSQL (live data)
        - Stripe API (payments)
        - Google Analytics API (user behavior)
        - Application logs (JSON format in S3)
        
        Requirements:
        - ETL pipeline running every hour
        - Transform and load into data warehouse (BigQuery? Snowflake?)
        - Aggregate metrics: MRR, churn rate, DAU/MAU, feature adoption
        - Historical data retention: 2 years
        - Query latency: < 2 seconds for dashboard
        
        Stack preferences: Python, Airflow, dbt
        """,
        "expected_skills": ["etl", "data-pipeline", "airflow", "bigquery", "analytics"],
        "expected_count": 7,
    },
    {
        "role": "DevOps Engineer",
        "mission": """
        Migrate from legacy VPS deployment to modern cloud infrastructure.
        
        Current state:
        - 3 VPS servers (OVH)
        - Manual deployments via SSH + rsync
        - No monitoring, no backups
        - Single point of failure
        
        Target state:
        - Kubernetes cluster (GKE or EKS)
        - GitOps with ArgoCD
        - Auto-scaling based on load
        - Multi-region for HA
        - Automated backups and disaster recovery
        - Infrastructure as Code (Terraform)
        - Observability (Prometheus, Grafana, Loki)
        - Cost optimization (~$500/month budget)
        
        Timeline: 6 weeks
        """,
        "expected_skills": ["kubernetes", "terraform", "gitops", "argocd", "monitoring", "cloud"],
        "expected_count": 8,
    },
]


# =============================================================================
# Test Runner
# =============================================================================


def test_mission(enhancer: AgentEnhancer, mission: dict, verbose: bool = False):
    """Test skills injection for a single mission."""
    print(f"\n{'=' * 80}")
    print(f"🎯 Testing: {mission['role']}")
    print(f"{'=' * 80}")

    if verbose:
        print("\n📋 Mission Context:")
        print(mission["mission"][:200] + "...")

    try:
        # Run enhancement
        result = enhancer.enhance_agent_prompt(
            base_system_prompt=f"You are an expert {mission['role']}.",
            mission_description=mission["mission"],
            agent_role=mission["role"],
            mission_id=f"test-{mission['role'].lower().replace(' ', '-')}",
            use_cache=True,
        )

        injected_skills = result.get("injected_skills", [])
        metadata = result.get("metadata", {})

        # Display results
        print("\n📊 Results:")
        print(f"  ✓ Skills injected: {len(injected_skills)}")
        print(f"  ✓ Context tokens: {metadata.get('context_tokens', 'N/A')}")
        print(f"  ✓ Matching method: {metadata.get('matching_method', 'N/A')}")
        print(f"  ✓ Cache hit: {metadata.get('cache_hit', False)}")

        if injected_skills:
            print("\n📚 Injected Skills:")
            for i, skill in enumerate(injected_skills[:5], 1):
                skill_id = skill.get("id", "unknown")
                title = skill.get("title", "No title")
                score = skill.get("score", 0.0)
                print(f"  {i}. [{skill_id}] {title} (score: {score:.3f})")

            if len(injected_skills) > 5:
                print(f"  ... and {len(injected_skills) - 5} more")

        # Validate expectations
        expected_count = mission.get("expected_count", 0)
        if len(injected_skills) < expected_count:
            print(f"\n⚠️  Warning: Expected ~{expected_count} skills, got {len(injected_skills)}")

        # Check for expected keywords in injected skills
        if verbose and mission.get("expected_skills"):
            print(f"\n🔍 Expected skill keywords: {', '.join(mission['expected_skills'])}")
            found_keywords = []
            for keyword in mission["expected_skills"]:
                for skill in injected_skills:
                    skill_text = f"{skill.get('title', '')} {skill.get('content', '')}".lower()
                    if keyword.lower() in skill_text:
                        found_keywords.append(keyword)
                        break

            if found_keywords:
                print(f"  ✓ Found: {', '.join(found_keywords)}")
            else:
                print("  ⚠️  No expected keywords found in injected skills")

        print(f"\n✅ Test passed for {mission['role']}")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        if verbose:
            import traceback

            traceback.print_exc()
        return False


def main():
    """Run all mission tests."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 80)
    print("🧪 Skills Injection - Real Mission Tests")
    print("=" * 80)

    # Initialize enhancer
    try:
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        azure_key = os.getenv("AZURE_OPENAI_KEY", "")
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "platform.db")

        if not all([azure_endpoint, azure_key]):
            print("\n⚠️  Azure OpenAI not configured. Tests will use fallback mode.")
            print("   Set these env vars for full testing:")
            print("   - AZURE_OPENAI_ENDPOINT")
            print("   - AZURE_OPENAI_KEY")

        enhancer = AgentEnhancer(
            db_path=db_path, azure_endpoint=azure_endpoint, azure_api_key=azure_key
        )

        print("\n✓ AgentEnhancer initialized")
        print("  Database: platform.db")
        print(f"  Skills loaded: {enhancer.storage.get_skills_count()}")

    except Exception as e:
        print(f"\n❌ Failed to initialize: {str(e)}")
        return 1

    # Run tests
    results = []
    for mission in TEST_MISSIONS:
        success = test_mission(enhancer, mission, verbose=verbose)
        results.append((mission["role"], success))

    # Summary
    print(f"\n{'=' * 80}")
    print("📊 Test Summary")
    print(f"{'=' * 80}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for role, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {role}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    print(f"\n⚠️  {total - passed} test(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
