from apis.utils.variants import is_variant_unlocked


def pick_recommended_decks(
    candidate_decks, owned_card_names, level_by_name,
    evolution_level_by_name, limit=3,
):
    """Score and rank candidate decks by playability for the owning player.

    `candidate_decks` is a list of dicts:
      {id, hash, count, card_ids: [...], evo_card_ids: [...],
       hero_card_ids: [...], cards: [{name, ...}]}
    where `cards` is the hydrated card list (already in render order).

    Returns the top `limit` decks ranked by:
       (1) fully playable (all required variants also unlocked) first,
       (2) then by average card level descending,
       (3) then by count (popularity) descending.

    Each result is the input dict augmented with:
      - avg_level, fully_playable, missing_variants
    """
    annotated = []
    for deck in candidate_decks:
        names = [c["name"] for c in deck["cards"]]
        if not names:
            continue
        if not all(n in owned_card_names for n in names):
            continue
        avg_level = sum(level_by_name[n] for n in names) / len(names)
        evo_set = set(deck["evo_card_ids"])
        hero_set = set(deck["hero_card_ids"])
        missing = []
        for card in deck["cards"]:
            card_id = card.get("id")
            variant = None
            if card_id is not None:
                if card_id in evo_set:
                    variant = "evolution"
                elif card_id in hero_set:
                    variant = "hero"
            if variant and not is_variant_unlocked(
                evolution_level_by_name.get(card["name"]), variant
            ):
                missing.append({
                    "name": card["name"],
                    "variant": variant,
                })
        annotated.append({
            **deck,
            "avg_level": round(avg_level, 1),
            "fully_playable": not missing,
            "missing_variants": missing,
        })
    annotated.sort(
        key=lambda d: (not d["fully_playable"], -d["avg_level"], -d["count"])
    )
    return annotated[:limit]
