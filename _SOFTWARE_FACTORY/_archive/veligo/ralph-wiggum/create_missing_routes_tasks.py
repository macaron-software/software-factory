#!/usr/bin/env python3
"""Create micro-tasks for missing frontend routes and gRPC stubs."""

from pathlib import Path

TASKS_DIR = Path("/Users/sylvain/_LAPOSTE/_VELIGO2/tools/ralph-wiggum/tasks")
STATUS_DIR = Path("/Users/sylvain/_LAPOSTE/_VELIGO2/tools/ralph-wiggum/status")
TASKS_DIR.mkdir(exist_ok=True)
STATUS_DIR.mkdir(exist_ok=True)

TASKS = [
    # ============ FRONTEND ROUTES (PRIORITARIES) ============
    # P0 - /booking - Complete reservation flow
    {
        "id": "T300",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/booking/+page.svelte",
        "title": "Implement complete /booking page",
        "desc": "Implement full booking flow: select bike/station, choose duration, confirm booking. Replace skeleton with real gRPC calls to bookingService",
    },
    {
        "id": "T301",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/booking/+page.server.ts",
        "title": "Add booking page server actions",
        "desc": "Add load function to fetch available bikes/stations, add actions for createBooking gRPC call",
    },
    # P0 - /stations - Station management & map
    {
        "id": "T302",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/stations/+page.svelte",
        "title": "Implement /stations page with map",
        "desc": "Replace skeleton with real station map using StationMapGeneric component, show real-time availability via gRPC StationService",
    },
    {
        "id": "T303",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/stations/+page.server.ts",
        "title": "Add stations page data loading",
        "desc": "Add load function to fetch stations via gRPC ListStations, handle station filtering by tenant",
    },
    # P0 - /checkout - Payment flow
    {
        "id": "T304",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/checkout/+page.svelte",
        "title": "Implement /checkout page payment flow",
        "desc": "Implement checkout page with payment method selection (Stripe, PayPal, etc.), order summary, confirm payment via gRPC PaymentService",
    },
    {
        "id": "T305",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/checkout/+page.server.ts",
        "title": "Add checkout page server actions",
        "desc": "Add load function for cart/order data, add action for createPayment gRPC call",
    },
    # P0 - /journey - Trip planner
    {
        "id": "T306",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/journey/+page.svelte",
        "title": "Implement /journey trip planner page",
        "desc": "Implement multimodal journey planner with origin/destination input, route options, bike/station suggestions. Connect to trip_planner service",
    },
    {
        "id": "T307",
        "priority": "P0",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/journey/+page.server.ts",
        "title": "Add journey planner server actions",
        "desc": "Add load function for transport options, add action for planning trips via gRPC",
    },
    # P1 - /admin-dashboard - Admin dashboard
    {
        "id": "T308",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/admin-dashboard/+page.svelte",
        "title": "Implement admin dashboard metrics",
        "desc": "Implement admin dashboard with real metrics: users, subscriptions, bikes, revenue. Add charts and real data via gRPC ReportService",
    },
    {
        "id": "T309",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/admin-dashboard/+page.server.ts",
        "title": "Add admin dashboard data loading",
        "desc": "Add load function to fetch dashboard stats via gRPC GetDashboardStats",
    },
    # P1 - /fleet - Fleet management
    {
        "id": "T310",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/fleet/+page.svelte",
        "title": "Implement /fleet management page",
        "desc": "Implement fleet management page with bike list, status, maintenance schedules, assignments",
    },
    {
        "id": "T311",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/fleet/+page.server.ts",
        "title": "Add fleet management server actions",
        "desc": "Add load function to fetch fleet data via gRPC BikeService, add actions for maintenance scheduling",
    },
    # P1 - /reports - Reports page
    {
        "id": "T312",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/reports/+page.svelte",
        "title": "Implement /reports page",
        "desc": "Implement reports page with report generation, listing, download via gRPC ReportService",
    },
    {
        "id": "T313",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/reports/+page.server.ts",
        "title": "Add reports server actions",
        "desc": "Add load function for reports list, add actions for generate/download reports",
    },
    # P1 - /settings - User settings
    {
        "id": "T314",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/settings/+page.svelte",
        "title": "Implement /settings page with real API",
        "desc": "Implement settings page with profile edit, password change, notification preferences, connected apps. Use real gRPC UserService calls",
    },
    {
        "id": "T315",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/settings/+page.server.ts",
        "title": "Add settings server actions",
        "desc": "Add actions for updateProfile, changePassword, updateNotifications via gRPC",
    },
    # P1 - /onboarding - Onboarding flow
    {
        "id": "T316",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/onboarding/+page.svelte",
        "title": "Implement /onboarding complete flow",
        "desc": "Implement complete onboarding: identity verification (FranceConnect), payment setup, preferences. Connect to real APIs",
    },
    {
        "id": "T317",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/onboarding/+page.server.ts",
        "title": "Add onboarding server actions",
        "desc": "Add actions for submitIdentity (via gRPC), submitPayment, completeOnboarding",
    },
    # P1 - /incidents - Incident reporting
    {
        "id": "T318",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/incidents/+page.svelte",
        "title": "Implement /incidents with real API",
        "desc": "Implement incident reporting page with form, list of user incidents, status tracking via real gRPC calls",
    },
    {
        "id": "T319",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/incidents/+page.server.ts",
        "title": "Add incidents server actions",
        "desc": "Add load function for user incidents, add action for createIncident via gRPC",
    },
    # P1 - /referral - Referral program
    {
        "id": "T320",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/referral/+page.svelte",
        "title": "Implement referral program with real API",
        "desc": "Implement referral program UI with referral code, invite friends, rewards tracking via real API endpoints",
    },
    {
        "id": "T321",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/referral/+page.server.ts",
        "title": "Add referral server actions",
        "desc": "Add load function for referral stats, add action for generateReferralCode, inviteFriend",
    },
    # P1 - /boxes - Bike boxes
    {
        "id": "T322",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/boxes/+page.svelte",
        "title": "Implement /boxes bike storage page",
        "desc": "Implement bike boxes management: list boxes, open box with QR scanner, reservation via real gRPC calls",
    },
    {
        "id": "T323",
        "priority": "P1",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(app)/boxes/+page.server.ts",
        "title": "Add boxes server actions",
        "desc": "Add load function for boxes list, add actions for createBox, openBox, startScanner via gRPC",
    },
    # P2 - Landing pages
    {
        "id": "T324",
        "priority": "P2",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(landing)/welcome-idfm/+page.svelte",
        "title": "Implement welcome-idfm landing page",
        "desc": "Implement IDFM welcome page with tenant branding, features, CTA to signup",
    },
    {
        "id": "T325",
        "priority": "P2",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(landing)/welcome-nantes/+page.svelte",
        "title": "Implement welcome-nantes landing page",
        "desc": "Implement Nantes welcome page with eco-journey features, local partnerships",
    },
    {
        "id": "T326",
        "priority": "P2",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(landing)/welcome-lyon/+page.svelte",
        "title": "Implement welcome-lyon landing page",
        "desc": "Implement Lyon welcome page with transit integration, multimodal planner",
    },
    # P2 - Admin themes & RGPD
    {
        "id": "T327",
        "priority": "P2",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/themes/+page.svelte",
        "title": "Implement /themes admin page",
        "desc": "Implement theme customization page for tenant branding: colors, logos, custom CSS",
    },
    {
        "id": "T328",
        "priority": "P2",
        "queue": "TDD",
        "file": "veligo-platform/frontend/src/routes/(admin)/rgpd/+page.svelte",
        "title": "Implement /rgpd admin compliance page",
        "desc": "Implement RGPD compliance dashboard: consent management, data export requests, deletion requests",
    },
    # ============ BACKEND gRPC STUBS ============
    # P0 - Trip Planner (TODO in trip_planner.rs:465)
    {
        "id": "T330",
        "priority": "P0",
        "queue": "TDD",
        "file": "backend/src/services/planner/trip_planner.rs",
        "title": "Load trip data from database",
        "desc": "Replace TODO at line 465 with actual database query to load stations, bikes, routes from PostgreSQL",
    },
    # P0 - Fraud Detection (multiple TODOs in fraud_detection.rs)
    {
        "id": "T331",
        "priority": "P0",
        "queue": "TDD",
        "file": "backend/src/jobs/fraud_detection.rs",
        "title": "Implement fraud detection job",
        "desc": "Implement fraud detection logic: T018 - Enable when fraud_detection_module is implemented. Add pattern detection, alerts",
    },
    # P1 - Reporting (TODO in report_routes.rs:769-771)
    {
        "id": "T332",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/services/reporting/report_routes.rs",
        "title": "Calculate avg_repair_time_hours and batteries_replaced",
        "desc": "Replace TODO at lines 769-771 with actual SQL queries to calculate metrics from maintenance records",
    },
    # P1 - Subscription workflow_actions
    {
        "id": "T333",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/application/commands/create_subscription.rs",
        "title": "Load workflow_actions from database",
        "desc": "Replace TODO at line 158 with actual database query to workflow_actions table for subscription onboarding steps",
    },
    # P1 - Document API subscription details
    {
        "id": "T334",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/api/document_api.rs",
        "title": "Fetch real subscription details for contracts",
        "desc": "Replace TODO at line 332 with actual database query to fetch subscription data for Cerfa contracts",
    },
    # P1 - Cerfa routes database query
    {
        "id": "T335",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/services/documents/cerfa_routes.rs",
        "title": "Replace mock with real database query",
        "desc": "Replace TODO at line 379 with actual database query to fetch user subscription data for Cerfa forms",
    },
    # P1 - Station operating hours
    {
        "id": "T336",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/infrastructure/database/repositories/stations/postgres_station_repository.rs",
        "title": "Implement station operating hours check",
        "desc": "Replace TODO at line 481 with actual database query to check station operating hours",
    },
    # P1 - Reward service distance calculation
    {
        "id": "T337",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/services/rewards/reward_service.rs",
        "title": "Calculate distance_meters for rewards",
        "desc": "Replace TODO at line 249 with actual distance calculation from booking history",
    },
    # P1 - Report templates comparison
    {
        "id": "T338",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/services/reporting/report_templates.rs",
        "title": "Implement quarter comparison",
        "desc": "Replace TODO at line 406 with actual comparison logic against previous quarter data",
    },
    # P1 - Module HTTP routes registration
    {
        "id": "T339",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/handlers/admin_owner.rs",
        "title": "Register HTTP routes for module T023",
        "desc": "Replace TODO at line 435 - Register HTTP routes for the module when module is activated",
    },
    # P1 - Module dependency check
    {
        "id": "T340",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/infrastructure/http/module_routes.rs",
        "title": "Check dependencies before module deactivation",
        "desc": "Replace TODO at line 137 - Check dependencies before allowing module deactivation",
    },
    # P1 - Module config validation
    {
        "id": "T341",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/infrastructure/http/module_routes.rs",
        "title": "Validate module config against JSON schema",
        "desc": "Replace TODO at line 212 - Validate module configuration against module JSON schema",
    },
    # P1 - Module tests
    {
        "id": "T342",
        "priority": "P1",
        "queue": "TDD",
        "file": "backend/src/infrastructure/http/module_routes.rs",
        "title": "Add module configuration tests",
        "desc": "Replace TODO at line 265 - Add tests for module configuration validation",
    },
    # P2 - Rate limiting via tonic interceptors
    {
        "id": "T343",
        "priority": "P2",
        "queue": "TDD",
        "file": "backend/src/bin/tonic-server.rs",
        "title": "Implement gRPC rate limiting",
        "desc": "Replace TODO at line 1715 - Implement rate limiting via tonic interceptors for gRPC server",
    },
    # P2 - Remove deprecated auth routes
    {
        "id": "T344",
        "priority": "P2",
        "queue": "TDD",
        "file": "backend/src/bin/http-server.rs",
        "title": "Remove deprecated /auth/* routes",
        "desc": "Replace TODO at line 226 - Remove /auth/* mounts after nginx config deployment",
    },
]

print(f"Creating {len(TASKS)} micro-tasks...")

for task in TASKS:
    task_file = TASKS_DIR / f"{task['id']}.md"
    status_file = STATUS_DIR / f"{task['id']}.status"

    wsjf = (
        "12"
        if task["priority"] == "P0"
        else ("10" if task["priority"] == "P1" else "6")
    )
    complexity = (
        "high"
        if task["priority"] == "P0"
        else ("medium" if task["priority"] == "P1" else "low")
    )

    content = f"""# Task {task["id"]}: {task["title"]}

**Priority**: {task["priority"]}
**Queue**: {task["queue"]}
**Type**: implementation

## File
{task["file"]}

## Description
{task["desc"]}

## Success Criteria
- [ ] Implementation complete
- [ ] cargo check passes (or npm run build for frontend)
- [ ] Unit/integration tests added
- [ ] No new warnings
- [ ] Works with gRPC calls (frontend) or database queries (backend)

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: {complexity}
WSJF: {wsjf}
---END_RALPH_STATUS---
"""
    task_file.write_text(content)
    status_file.write_text("PENDING\n")
    print(f"  Created {task['id']}: {task['title'][:50]}...")

print(f"\nDone: {len(TASKS)} tasks created (T300-T344)")
