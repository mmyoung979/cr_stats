from apis.utils.variants import is_variant_unlocked, slot_active_variant


def pick_recommended_decks(
    all_decks, owned_card_names, level_by_name, evolution_level_by_name, limit=3
):
    """Top `limit` decks the player owns all base cards for, ranked by:
       (1) fully playable (all required variants also unlocked) first,
       (2) then by count descending.

    Each result is the input deck dict augmented with:
      - `avg_level`: mean of `level_by_name[name]` across the deck's cards (1 dp)
      - `fully_playable`: True iff `missing_variants` is empty
      - `missing_variants`: list of {name, slot, variant} for slots whose active
        variant the player has not unlocked.
    Sort is stable on the secondary key — ties preserve input order.
    """
    annotated = []
    for deck in all_decks:
        names = [c["name"] for c in deck["cards"]]
        if not names:
            continue
        if not all(n in owned_card_names for n in names):
            continue
        avg_level = sum(level_by_name[n] for n in names) / len(names)
        missing = []
        for slot_idx, card in enumerate(deck["cards"]):
            variant = slot_active_variant(
                slot_idx, card.get("hasEvolution"), card.get("hasHero")
            )
            if variant and not is_variant_unlocked(
                evolution_level_by_name.get(card["name"]), variant
            ):
                missing.append(
                    {"name": card["name"], "slot": slot_idx, "variant": variant}
                )
        annotated.append({
            **deck,
            "avg_level": round(avg_level, 1),
            "fully_playable": not missing,
            "missing_variants": missing,
        })
    annotated.sort(key=lambda d: (not d["fully_playable"], -d["count"]))
    return annotated[:limit]
