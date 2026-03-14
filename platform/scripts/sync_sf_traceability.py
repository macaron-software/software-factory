#!/usr/bin/env python3
"""
Sync SF SAFe traceability into PG — one-shot seed.

Reads SAFE_MAP from retro_sf_safe.py and creates:
  - 10 epics in missions table (if not exist)
  - 43 features with feat-{8hex} IDs
  - 154 user stories with us-{8hex} IDs
  - AC (Gherkin GIVEN/WHEN/THEN) for each story → ac-{8hex}

Run:  python3 platform/scripts/sync_sf_traceability.py
"""
# Ref: feat-annotate, feat-quality
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from platform.scripts.retro_sf_safe import SAFE_MAP  # type: ignore
from platform.missions.product import ProductBacklog, FeatureDef, UserStoryDef  # type: ignore
from platform.traceability.artifacts import (  # type: ignore
    get_ac_store, AcceptanceCriterion, make_id,
)

PROJECT_ID = "sf-platform"


def _story_to_ac(story_text: str, feature_name: str) -> dict:
    """Generate Gherkin AC from a story description (deterministic, no LLM)."""
    # Simple heuristic: derive GIVEN/WHEN/THEN from story text
    story = story_text.strip()

    # Pattern: "Verbe + complément" → GIVEN user on page, WHEN action, THEN result
    if story.lower().startswith(("voir ", "consulter ", "afficher ")):
        return {
            "given": f"un utilisateur authentifie sur la page {feature_name}",
            "when": f"la page se charge",
            "then": story,
        }
    elif story.lower().startswith(("lancer ", "demarrer ", "creer ", "créer ", "generer ", "générer ")):
        return {
            "given": f"un utilisateur sur la page {feature_name}",
            "when": f"l'utilisateur clique sur le bouton d'action",
            "then": story,
        }
    elif story.lower().startswith(("naviguer ", "acceder ", "accéder ")):
        return {
            "given": f"un utilisateur sur le cockpit ou la navigation",
            "when": f"l'utilisateur clique sur le lien",
            "then": story,
        }
    elif story.lower().startswith(("filtrer ", "trier ", "rechercher ", "chercher ")):
        return {
            "given": f"une liste affichee sur la page {feature_name}",
            "when": f"l'utilisateur applique un filtre ou une recherche",
            "then": story,
        }
    elif story.lower().startswith(("exporter ", "telecharger ", "télécharger ")):
        return {
            "given": f"des donnees disponibles sur la page {feature_name}",
            "when": f"l'utilisateur clique sur exporter",
            "then": story,
        }
    elif story.lower().startswith(("configurer ", "parametrer ", "modifier ")):
        return {
            "given": f"un administrateur sur la page {feature_name}",
            "when": f"l'utilisateur modifie la configuration",
            "then": story,
        }
    else:
        return {
            "given": f"un utilisateur sur la page {feature_name}",
            "when": f"l'utilisateur interagit avec l'interface",
            "then": story,
        }


def main():
    pb = ProductBacklog()
    ac_store = get_ac_store()

    total_features = 0
    total_stories = 0
    total_ac = 0

    for epic in SAFE_MAP:
        epic_id = epic["id"]
        print(f"\n{'='*60}")
        print(f"Epic: {epic_id} — {epic['name']}")
        print(f"{'='*60}")

        for feat_data in epic["features"]:
            # Check if feature already exists
            existing = pb.list_features(epic_id)
            if any(f.id == feat_data["id"] for f in existing):
                print(f"  [SKIP] {feat_data['id']} already exists")
                continue

            # Create feature
            feat = pb.create_feature(FeatureDef(
                id=feat_data["id"],
                epic_id=epic_id,
                name=feat_data["name"],
                description=feat_data.get("description", ""),
                priority=5,
                status="backlog",
                persona_id=feat_data.get("persona", ""),
            ))
            total_features += 1
            print(f"  [FEAT] {feat.id} — {feat.name} (persona: {feat_data.get('persona', '—')})")

            # Create stories + AC
            for story_text in feat_data.get("stories", []):
                story = pb.create_story(UserStoryDef(
                    feature_id=feat.id,
                    title=story_text,
                    description=f"En tant que {feat_data.get('persona', 'utilisateur')}, je veux {story_text.lower()}",
                    priority=5,
                    status="backlog",
                ))
                total_stories += 1

                # Generate AC from story
                ac_data = _story_to_ac(story_text, feat.name)
                ac = ac_store.create(AcceptanceCriterion(
                    feature_id=feat.id,
                    story_id=story.id,
                    title=story_text[:100],
                    given_text=ac_data["given"],
                    when_text=ac_data["when"],
                    then_text=ac_data["then"],
                ))
                total_ac += 1
                print(f"    [US]  {story.id} — {story_text[:60]}...")
                print(f"    [AC]  {ac.id} — GIVEN {ac_data['given'][:40]}...")

    print(f"\n{'='*60}")
    print(f"SYNC COMPLETE")
    print(f"  Features: {total_features}")
    print(f"  Stories:  {total_stories}")
    print(f"  AC:       {total_ac}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
