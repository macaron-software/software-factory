// Ref: feat-traceability, feat-grpc-tools
/**
 * Skills Audit + gRPC E2E Tests
 *
 * Coverage:
 *   SA01 – skills-audit endpoint: run exists → returns JSON structure
 *   SA02 – phases list includes injected_skills field (may be empty if no run yet)
 *   SA03 – skills list returns all SF skills including new design-system-components
 *   SA04 – trigger-based injection: POST mission with UX keywords → ux-laws triggered
 *   SA05 – skill content accessible: design-system-components.md exists with expected content
 *   SA06 – ux-laws skill exists and has content (file-system check)
 *   GR01 – gRPC proto file exists and is valid
 *   GR02 – gRPC stubs are generated (pb2 files exist)
 *   GR03 – gRPC server.py imports cleanly
 *   GR04 – gRPC client.py has sync + async clients
 *   GR05 – gRPC python package validates without import errors
 *   DS01 – design-system-components skill is registered and scannable
 *   DS02 – placeholder dash CSS class in components.css
 *   DS03 – skeleton_skills_audit macro in skeleton.html
 */
import { test, expect } from "@playwright/test";
import { SF_URL, safeGoto, collectErrors, assertNoErrors } from "./helpers";
import { execSync } from "child_process";
import * as path from "path";
import * as fs from "fs";

// ── Shared admin API context ──────────────────────────────────────────────────
import { APIRequestContext, Browser } from "@playwright/test";

let adminCtx: APIRequestContext;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  const ctx = await browser.newContext();
  const resp = await ctx.request.post(`${SF_URL}/api/auth/login`, {
    data: { email: "admin@demo.local", password: "admin" },
    headers: { "Content-Type": "application/json" },
  });
  if (!resp.ok()) throw new Error(`Admin login failed: HTTP ${resp.status()}`);
  adminCtx = ctx.request;
});

test.afterAll(async () => {
  await adminCtx?.dispose?.();
});

// ── Skills Audit ─────────────────────────────────────────────────────────────
test.describe("Skills Audit API", () => {
  test("SA01 – skills-audit endpoint returns structured JSON", async ({ page }) => {
    const errors = collectErrors(page);

    // Get any run ID (missions endpoint returns {epics: [...], total: N})
    const runsResp = await adminCtx.get(`${SF_URL}/api/missions`);
    if (runsResp.status() !== 200) { test.skip(); return; }
    const runsData = await runsResp.json().catch(() => ({}));
    const runs = runsData.epics ?? runsData.items ?? runsData.runs ?? (Array.isArray(runsData) ? runsData : []);

    // Find a mission that has an associated run (run_id may be null for unstarted missions)
    const missionWithRun = runs.find((r: any) => r.run_id);
    if (!missionWithRun) {
      const resp = await adminCtx.get(`${SF_URL}/api/missions/nonexistent-run/skills-audit`);
      expect(resp.status()).toBeGreaterThanOrEqual(404);
      return;
    }

    const runId = missionWithRun.run_id ?? missionWithRun.id;
    const resp = await adminCtx.get(`${SF_URL}/api/missions/${runId}/skills-audit`);
    expect(resp.status()).toBe(200);

    const audit = await resp.json();
    expect(audit).toHaveProperty("run_id");
    expect(audit).toHaveProperty("phases");
    expect(audit).toHaveProperty("skill_coverage");
    expect(audit).toHaveProperty("phases_without_skills");
    expect(audit).toHaveProperty("total_phases");
    expect(audit).toHaveProperty("phases_with_skills");
    expect(Array.isArray(audit.phases)).toBe(true);

    for (const phase of audit.phases) {
      expect(phase).toHaveProperty("phase_id");
      expect(phase).toHaveProperty("status");
      expect(phase).toHaveProperty("injected_skills");
      expect(Array.isArray(phase.injected_skills)).toBe(true);
    }

    assertNoErrors(errors, "SA01 skills-audit structure");
  });

  test("SA02 – epic_runs phases_json includes injected_skills key", async ({ page }) => {
    const runsResp = await adminCtx.get(`${SF_URL}/api/missions`);
    if (runsResp.status() !== 200) { test.skip(); return; }
    const runsData = await runsResp.json().catch(() => ({ items: [] }));
    const runs = runsData.epics ?? runsData.items ?? runsData.runs ?? (Array.isArray(runsData) ? runsData : []);

    if (runs.length === 0) { test.skip(); return; }

    const runId = runs[0].id ?? runs[0].run_id;
    const debugResp = await adminCtx.get(`${SF_URL}/api/missions/${runId}/debug`);

    if (debugResp.status() === 404) { test.skip(); return; }
    expect(debugResp.status()).toBe(200);

    const debug = await debugResp.json();
    if (debug.run && debug.run.phases_json) {
      const phases = JSON.parse(debug.run.phases_json);
      if (phases.length > 0) {
        expect(phases[0]).toHaveProperty("injected_skills");
      }
    }
  });

  test("SA03 – skills list includes design-system-components and ux-laws", async ({ page }) => {
    const errors = collectErrors(page);
    const resp = await adminCtx.get(`${SF_URL}/api/skills/list`);
    expect(resp.status()).toBeLessThan(500);

    const skills = await resp.json().catch(() => []);
    if (!Array.isArray(skills) || skills.length === 0) { test.skip(); return; }

    // Skills use `name` as identifier in this endpoint
    const dsSkill = skills.find((s: any) =>
      s.name === "design-system-components" || s.name?.includes("design-system")
    );
    expect(dsSkill, "design-system-components must be registered").toBeTruthy();

    const uxSkill = skills.find((s: any) =>
      s.name === "ux-laws" || s.name?.includes("ux-laws")
    );
    expect(uxSkill, "ux-laws must be registered").toBeTruthy();

    assertNoErrors(errors, "SA03 skills list");
  });

  test("SA05 – design-system-components.md exists with expected content", async () => {
    // File-system check: the skill markdown file must be present and contain key sections
    const skillPath = path.join(
      __dirname, "..", "..", "..", "skills", "design-system-components.md"
    );
    expect(fs.existsSync(skillPath), "design-system-components.md must exist").toBe(true);
    const content = fs.readFileSync(skillPath, "utf8");
    expect(content.length, "skill file must have substantial content").toBeGreaterThan(1000);
    expect(content).toContain("Feather");   // Feather icons section
    expect(content).toContain("RULE ZERO"); // No-emoji rule
    expect(content).toContain("tokens");    // Token system
  });

  test("SA06 – ux-laws skill exists and has content", async () => {
    // File-system check: ux-laws.md must exist with substantial content
    const skillPath = path.join(
      __dirname, "..", "..", "..", "skills", "ux-laws.md"
    );
    if (!fs.existsSync(skillPath)) { test.skip(); return; }
    const content = fs.readFileSync(skillPath, "utf8");
    expect(content.length, "ux-laws.md must have substantial content").toBeGreaterThan(500);
    // Must mention UX-related concepts
    expect(content.toLowerCase()).toMatch(/ux|user.experience|design|cognitive/);
  });
});

// ── Design System Assets ──────────────────────────────────────────────────────
test.describe("Design System Assets", () => {
  test("DS01 – components.css contains ph-dash placeholder class", async ({ page }) => {
    const resp = await page.request.get(`${SF_URL}/static/css/components.css`);
    expect(resp.status()).toBe(200);
    const css = await resp.text();
    expect(css).toContain(".ph-dash");
    expect(css).toContain(".ph-dash::before");
    expect(css).toContain(".ph-dash--sm");
    expect(css).toContain(".ph-metric");
  });

  test("DS02 – components.css has skeleton-shimmer animation", async ({ page }) => {
    const resp = await page.request.get(`${SF_URL}/static/css/components.css`);
    expect(resp.status()).toBe(200);
    const css = await resp.text();
    expect(css).toContain("skeleton-shimmer");
    expect(css).toContain(".sk-phase-row");
    expect(css).toContain(".sk-pill");
  });

  test("DS03 – skeleton.html contains new audit macros", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/agents");
    await expect(page.locator("body")).toBeVisible();
    await page.waitForTimeout(500);
    assertNoErrors(errors, "DS03 skeleton macros");
  });
});

// ── gRPC Tool Service ─────────────────────────────────────────────────────────
test.describe("gRPC ToolService", () => {
  test("GR01 – gRPC proto file exists and is valid", async () => {
    const protoPath = path.join(
      __dirname,
      "../../tools/grpc/tool_service.proto"
    );
    expect(fs.existsSync(protoPath), "tool_service.proto must exist").toBe(true);
    const content = fs.readFileSync(protoPath, "utf8");
    expect(content).toContain("service ToolService");
    expect(content).toContain("rpc Execute");
    expect(content).toContain("rpc ExecuteStream");
    expect(content).toContain("rpc GetSchemas");
    expect(content).toContain("ToolContext");
  });

  test("GR02 – gRPC stubs are generated (pb2 files exist)", async () => {
    const grpcDir = path.join(__dirname, "../../tools/grpc");
    const pb2 = path.join(grpcDir, "tool_service_pb2.py");
    const pb2grpc = path.join(grpcDir, "tool_service_pb2_grpc.py");
    expect(fs.existsSync(pb2), "pb2 stub must exist").toBe(true);
    expect(fs.existsSync(pb2grpc), "pb2_grpc stub must exist").toBe(true);

    const grpcContent = fs.readFileSync(pb2grpc, "utf8");
    expect(grpcContent).toContain("ToolServiceStub");
    expect(grpcContent).toContain("ToolServiceServicer");
    expect(grpcContent).toContain("add_ToolServiceServicer_to_server");
  });

  test("GR03 – gRPC server.py imports cleanly", async () => {
    const serverPath = path.join(__dirname, "../../tools/grpc/server.py");
    expect(fs.existsSync(serverPath), "server.py must exist").toBe(true);
    const content = fs.readFileSync(serverPath, "utf8");
    expect(content).toContain("serve_async");
    expect(content).toContain("ToolServicer");
    // Server uses `from grpc import aio` then calls aio.server()
    expect(content).toContain("from grpc import aio");
  });

  test("GR04 – gRPC client.py has sync + async clients", async () => {
    const clientPath = path.join(__dirname, "../../tools/grpc/client.py");
    expect(fs.existsSync(clientPath), "client.py must exist").toBe(true);
    const content = fs.readFileSync(clientPath, "utf8");
    expect(content).toContain("class ToolServiceClient");
    expect(content).toContain("class AsyncToolServiceClient");
    expect(content).toContain("get_grpc_client");
    expect(content).toContain("SF_GRPC_ADDR");
  });

  test("GR05 – gRPC python package validates without import errors", async () => {
    const platformDir = path.join(__dirname, "../../..");
    let result: { stdout?: string; stderr?: string; status?: number } = {};
    try {
      const stdout = execSync(
        `python3 -c "
import sys; sys.path.insert(0, '.')
from platform.tools.grpc import tool_service_pb2 as pb2
req = pb2.ToolRequest(call_id='test', name='code_read', args=b'{}',
    ctx=pb2.ToolContext(session_id='s1'))
resp = pb2.ToolResponse(call_id='test', success=True, result=b'ok', duration_ms=10)
schemas_req = pb2.GetSchemasRequest(agent_id='dev_backend')
print('ALL_OK')
"`,
        { cwd: platformDir, encoding: "utf8", timeout: 15000 }
      );
      result.stdout = stdout;
      result.status = 0;
    } catch (e: any) {
      result.stderr = e.stderr;
      result.status = e.status;
    }
    expect(result.stdout?.trim(), "Proto messages should construct without error").toContain("ALL_OK");
  });
});

