#!/usr/bin/env python3
"""
Generate photorealistic profile photo avatars for all platform agents.

Usage:
    # With Azure OpenAI DALL-E 3:
    AZURE_OPENAI_API_KEY=<key> AZURE_OPENAI_ENDPOINT=<url> python3 scripts/generate_avatars.py

    # With OpenAI directly:
    OPENAI_API_KEY=<key> python3 scripts/generate_avatars.py

    # Skip existing JPG files (only generate missing ones):
    python3 scripts/generate_avatars.py --missing-only

    # Generate for a single agent:
    python3 scripts/generate_avatars.py --agent llm-ops-engineer
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from platform.agents.store import get_agent_store

AVATAR_DIR = Path(__file__).parent.parent / "platform" / "web" / "static" / "avatars"

# Detailed prompts per agent type for better DALL-E results
ROLE_PROMPTS = {
    "cto": "professional headshot, CTO, male, 40s, confident, business casual, tech executive",
    "cpo": "professional headshot, CPO, female, 38, sharp, executive, modern office background",
    "product-manager": "professional headshot, product manager, 30s, friendly, startup vibes",
    "developer": "professional headshot, software developer, 28-35, casual professional, tech",
    "security": "professional headshot, cybersecurity expert, serious expression, dark background",
    "data": "professional headshot, data scientist, analytical, 30s, professional",
    "ux": "professional headshot, UX designer, creative, 28-35, modern aesthetic",
    "qa": "professional headshot, QA engineer, 28-35, precise, focused",
    "devops": "professional headshot, DevOps engineer, 30s, technical, infrastructure background",
    "architect": "professional headshot, software architect, 40s, thoughtful, senior",
    "manager": "professional headshot, engineering manager, 35-45, leadership, corporate",
    "ml": "professional headshot, ML engineer, AI researcher, 30s, technical",
    "default": "professional headshot portrait, software professional, natural lighting, white background",
}

FEMALE_NAMES = {
    "sophie",
    "camille",
    "emma",
    "marie",
    "léa",
    "lea",
    "nadia",
    "isabelle",
    "claire",
    "chloé",
    "chloe",
    "virginie",
    "sarah",
    "julie",
    "fatima",
    "diane",
    "caroline",
    "manon",
    "patricia",
    "émilie",
    "emilie",
    "inès",
    "ines",
    "noémie",
    "noemie",
    "samira",
    "yasmine",
    "jade",
    "elise",
    "élise",
    "nathalie",
    "ariane",
    "laura",
    "alice",
    "marine",
    "pauline",
    "audrey",
    "celine",
    "solène",
    "amandine",
    "lucie",
    "margaux",
    "charlotte",
    "amélie",
    "amelie",
    "chloé",
    "mathilde",
    "justine",
    "delphine",
    "christelle",
    "maud",
    "gaelle",
    "gaëlle",
    "laurie",
    "élodie",
    "elodie",
    "lisa",
    "eva",
    "zoe",
    "zoé",
    "victoria",
    "florence",
    "véronique",
    "veronique",
    "sylvie",
    "corinne",
    "laurence",
    "laetitia",
}

SKIN_DESCRIPTORS = [
    "light skin",
    "medium skin",
    "olive skin",
    "brown skin",
    "dark skin",
    "fair skin",
    "tan skin",
    "warm medium skin",
]

ORIGIN_DESCRIPTORS = [
    "French",
    "French-African",
    "French-Arab",
    "French-Asian",
    "French-Caribbean",
    "European",
    "North African",
    "West African",
    "French-South Asian",
]


def get_agent_prompt(agent_id: str, agent_name: str, agent_role: str) -> str:
    """Build a detailed DALL-E prompt for a specific agent."""
    import hashlib

    def h(s: str, n: int) -> int:
        return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % n

    first_name = (agent_name or "").split()[0].lower()
    is_female = first_name in FEMALE_NAMES
    gender = "woman" if is_female else "man"

    # Age range based on role seniority
    role_lower = (agent_role or "").lower()
    if any(
        w in role_lower
        for w in [
            "lead",
            "senior",
            "principal",
            "chief",
            "director",
            "cto",
            "ciso",
            "cpo",
            "cmo",
        ]
    ):
        age = "40s"
    elif any(w in role_lower for w in ["manager", "architect", "owner", "engineer"]):
        age = "35-45"
    else:
        age = "28-38"

    skin = SKIN_DESCRIPTORS[h(agent_id, len(SKIN_DESCRIPTORS))]
    origin = ORIGIN_DESCRIPTORS[h(agent_id + "orig", len(ORIGIN_DESCRIPTORS))]

    # Role-specific context
    if any(w in role_lower for w in ["cto", "cpo", "chief"]):
        style = "business professional attire, executive headshot"
        bg = "blurred modern office background"
    elif any(w in role_lower for w in ["security", "ciso", "pentest"]):
        style = "smart casual, professional, focused expression"
        bg = "dark neutral background"
    elif any(w in role_lower for w in ["ux", "design", "brand"]):
        style = "creative casual, modern aesthetic"
        bg = "light studio background"
    elif any(w in role_lower for w in ["data", "ml", "ai", "analytics"]):
        style = "business casual, analytical expression"
        bg = "neutral professional background"
    elif any(w in role_lower for w in ["devops", "cloud", "infra", "sre"]):
        style = "smart casual, technical professional"
        bg = "clean neutral background"
    else:
        style = "business casual attire"
        bg = "light professional background"

    prompt = (
        f"Professional LinkedIn-style headshot portrait photo of a {age} {origin} {gender} "
        f"with {skin}. {style}. {bg}. "
        f"Natural soft lighting, sharp focus on face, photorealistic, 4K quality. "
        f"Person named {agent_name} working as {agent_role}. "
        f"Friendly confident professional expression. Not AI generated looking."
    )
    return prompt


async def generate_with_azure(agent_id: str, prompt: str) -> bytes | None:
    """Generate image using Azure OpenAI DALL-E 3."""
    import httpx

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "") or os.environ.get(
        "AZURE_OPENAI_KEY", ""
    )

    if not api_key:
        # Try reading from key file
        key_file = Path.home() / ".config" / "factory" / "azure-openai.key"
        if key_file.exists():
            api_key = key_file.read_text().strip()

    if not api_key or not endpoint:
        return None

    deployment = os.environ.get("AZURE_DALLE_DEPLOYMENT", "dall-e-3")
    url = f"{endpoint}/openai/deployments/{deployment}/images/generations?api-version=2024-05-01-preview"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
                "style": "natural",
                "response_format": "b64_json",
            },
        )
        if resp.status_code != 200:
            print(f"  Azure error {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        b64 = data["data"][0].get("b64_json", "")
        return base64.b64decode(b64) if b64 else None


async def generate_with_openai(agent_id: str, prompt: str) -> bytes | None:
    """Generate image using OpenAI DALL-E 3."""
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
                "style": "natural",
                "response_format": "b64_json",
            },
        )
        if resp.status_code != 200:
            print(f"  OpenAI error {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        b64 = data["data"][0].get("b64_json", "")
        return base64.b64decode(b64) if b64 else None


async def generate_avatar(agent_id: str, agent_name: str, agent_role: str) -> bool:
    """Generate and save an avatar for an agent. Returns True on success."""
    prompt = get_agent_prompt(agent_id, agent_name, agent_role)
    print(f"  Generating: {agent_id} ({agent_name})...")

    # Try Azure first, then OpenAI
    image_data = await generate_with_azure(agent_id, prompt)
    if not image_data:
        image_data = await generate_with_openai(agent_id, prompt)

    if not image_data:
        print(f"  SKIP: No image API available for {agent_id}")
        return False

    out_path = AVATAR_DIR / f"{agent_id}.jpg"
    out_path.write_bytes(image_data)
    print(f"  Saved: {out_path.name} ({len(image_data) // 1024}KB)")
    return True


async def main():
    parser = argparse.ArgumentParser(description="Generate agent profile photos")
    parser.add_argument(
        "--missing-only", action="store_true", help="Only generate missing avatars"
    )
    parser.add_argument("--agent", help="Generate for a specific agent ID only")
    parser.add_argument(
        "--delay", type=float, default=2.0, help="Delay between requests (seconds)"
    )
    args = parser.parse_args()

    store = get_agent_store()
    agents = store.list_all()

    if args.agent:
        agents = [a for a in agents if a.id == args.agent]
        if not agents:
            print(f"Agent '{args.agent}' not found")
            sys.exit(1)

    to_generate = []
    for agent in agents:
        jpg = AVATAR_DIR / f"{agent.id}.jpg"
        if args.missing_only and jpg.exists():
            continue
        to_generate.append(agent)

    print(f"Generating {len(to_generate)} avatars...")
    print(f"Avatar dir: {AVATAR_DIR}")

    # Check API availability
    has_azure = bool(
        (
            os.environ.get("AZURE_OPENAI_API_KEY")
            or (Path.home() / ".config/factory/azure-openai.key").exists()
        )
        and os.environ.get("AZURE_OPENAI_ENDPOINT")
    )
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    if not has_azure and not has_openai:
        print("\nNo image generation API configured!")
        print("Set AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT, or OPENAI_API_KEY")
        print("\nSVG fallback avatars are already generated at:")
        print(f"  {AVATAR_DIR}/*.svg")
        sys.exit(1)

    success = 0
    for i, agent in enumerate(to_generate):
        if i > 0:
            time.sleep(args.delay)
        ok = await generate_avatar(agent.id, agent.name or agent.id, agent.role or "")
        if ok:
            success += 1

    print(f"\nDone: {success}/{len(to_generate)} avatars generated")


if __name__ == "__main__":
    asyncio.run(main())
