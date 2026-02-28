"""Agent Evaluation Framework — datasets, cases, runs, LLM-as-judge scoring."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ...db.migrations import get_db

router = APIRouter()
templates = Jinja2Templates(directory="platform/web/templates")


# ── Pages ────────────────────────────────────────────────────────────────────


@router.get("/evals", response_class=HTMLResponse)
async def evals_page(request: Request):
    return templates.TemplateResponse(
        request, "evals.html", {"page_title": "Evaluations"}
    )


# ── Datasets ─────────────────────────────────────────────────────────────────


@router.get("/api/evals/datasets")
async def list_datasets():
    db = get_db()
    rows = db.execute("SELECT * FROM eval_datasets ORDER BY created_at DESC").fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.post("/api/evals/datasets")
async def create_dataset(request: Request):
    body = await request.json()
    ds_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO eval_datasets (id, name, description, agent_id) VALUES (?,?,?,?)",
        (
            ds_id,
            body.get("name", "Untitled"),
            body.get("description", ""),
            body.get("agent_id", ""),
        ),
    )
    db.commit()
    return JSONResponse({"id": ds_id})


# ── Cases ─────────────────────────────────────────────────────────────────────


@router.get("/api/evals/datasets/{dataset_id}/cases")
async def list_cases(dataset_id: str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM eval_cases WHERE dataset_id=? ORDER BY created_at",
        (dataset_id,),
    ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.post("/api/evals/datasets/{dataset_id}/cases")
async def add_case(dataset_id: str, request: Request):
    body = await request.json()
    case_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO eval_cases (id, dataset_id, prompt, expected_output, tags) VALUES (?,?,?,?,?)",
        (
            case_id,
            dataset_id,
            body.get("prompt", ""),
            body.get("expected_output", ""),
            json.dumps(body.get("tags", [])),
        ),
    )
    db.commit()
    return JSONResponse({"id": case_id})


@router.delete("/api/evals/cases/{case_id}")
async def delete_case(case_id: str):
    db = get_db()
    db.execute("DELETE FROM eval_cases WHERE id=?", (case_id,))
    db.commit()
    return JSONResponse({"ok": True})


# ── Runs ──────────────────────────────────────────────────────────────────────


@router.get("/api/evals/runs")
async def list_runs():
    db = get_db()
    rows = db.execute(
        "SELECT r.*, d.name as dataset_name FROM eval_runs r "
        "LEFT JOIN eval_datasets d ON r.dataset_id=d.id "
        "ORDER BY r.created_at DESC LIMIT 50"
    ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.post("/api/evals/runs")
async def start_run(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    dataset_id = body.get("dataset_id", "")
    agent_id = body.get("agent_id", "")
    run_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO eval_runs (id, dataset_id, agent_id, status) VALUES (?,?,?,'running')",
        (run_id, dataset_id, agent_id),
    )
    db.commit()
    background_tasks.add_task(_execute_run, run_id, dataset_id, agent_id)
    return JSONResponse({"id": run_id})


@router.get("/api/evals/runs/{run_id}/results")
async def get_run_results(run_id: str):
    db = get_db()
    run = db.execute("SELECT * FROM eval_runs WHERE id=?", (run_id,)).fetchone()
    results = db.execute(
        "SELECT r.*, c.prompt, c.expected_output FROM eval_results r "
        "LEFT JOIN eval_cases c ON r.case_id=c.id WHERE r.run_id=? ORDER BY r.created_at",
        (run_id,),
    ).fetchall()
    return JSONResponse(
        {
            "run": dict(run) if run else {},
            "results": [dict(r) for r in results],
        }
    )


async def _execute_run(run_id: str, dataset_id: str, agent_id: str):
    """Background: run each case through the agent + LLM-as-judge scoring."""
    try:
        from ...llm.client import get_llm_client

        db = get_db()
        cases = db.execute(
            "SELECT * FROM eval_cases WHERE dataset_id=?", (dataset_id,)
        ).fetchall()

        scores = []
        for case in cases:
            result_id = str(uuid.uuid4())
            actual_output = ""
            score = 0.5
            feedback = ""
            t0 = time.time()
            try:
                # Run agent via LLM client directly with the prompt
                client = get_llm_client()
                resp = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.complete(
                        messages=[{"role": "user", "content": case["prompt"]}],
                        agent_id=agent_id or "worker",
                    ),
                )
                actual_output = (
                    resp.get("content", "") if isinstance(resp, dict) else str(resp)
                )

                # LLM-as-judge
                if case["expected_output"]:
                    judge_prompt = (
                        f"Score de 0 à 10 la pertinence de cette réponse par rapport à la réponse attendue.\n"
                        f"Réponse attendue: {case['expected_output'][:500]}\n"
                        f"Réponse obtenue: {actual_output[:500]}\n"
                        f'Réponds avec un JSON: {{"score": <0-10>, "feedback": "<raison>"}}'
                    )
                    judge_resp = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.complete(
                            messages=[{"role": "user", "content": judge_prompt}],
                            agent_id="eval-judge",
                        ),
                    )
                    judge_content = (
                        judge_resp.get("content", "{}")
                        if isinstance(judge_resp, dict)
                        else "{}"
                    )
                    try:
                        judge_json = json.loads(judge_content)
                        score = float(judge_json.get("score", 5)) / 10.0
                        feedback = judge_json.get("feedback", "")
                    except Exception:
                        score = 0.5
            except Exception as e:
                actual_output = f"[error: {e}]"
                score = 0.0
                feedback = str(e)

            latency_ms = int((time.time() - t0) * 1000)
            db.execute(
                "INSERT INTO eval_results (id, run_id, case_id, actual_output, score, judge_feedback, latency_ms) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    result_id,
                    run_id,
                    case["id"],
                    actual_output,
                    score,
                    feedback,
                    latency_ms,
                ),
            )
            db.commit()
            scores.append(score)

        avg = sum(scores) / len(scores) if scores else 0.0
        db.execute(
            "UPDATE eval_runs SET status='completed', score_avg=?, completed_at=datetime('now') WHERE id=?",
            (avg, run_id),
        )
        db.commit()
    except Exception:
        db = get_db()
        db.execute("UPDATE eval_runs SET status='failed' WHERE id=?", (run_id,))
        db.commit()
