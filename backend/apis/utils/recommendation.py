from apis.utils.variants import is_variant_unlocked

# --- Recommendation scoring knobs -------------------------------------------
# A deck's rank is a weighted blend of (confidence-adjusted) win rate, average
# card level, and how many games back the win rate. Tune these to taste.
WIN_RATE_WEIGHT = 0.6
LEVEL_WEIGHT = 0.3
GAMES_WEIGHT = 0.1

# Win rate is shrunk toward PRIOR_WIN_RATE using SHRINKAGE_GAMES pseudo-games,
# so a great record over few games isn't trusted like one over many. With
# K=20: a 7-3 deck (70% over 10 games) shrinks to ~57%, while a 140-60 deck
# (70% over 200 games) stays ~68%.
PRIOR_WIN_RATE = 0.5
SHRINKAGE_GAMES = 20

# Games-played credit saturates here; beyond this the sample is "enough".
FULL_CONFIDENCE_GAMES = 50

# Displayed in-game level cap (see MAX_DISPLAYED_LEVEL in player.py).
MAX_LEVEL = 16


def _deck_score(avg_level, wins, losses):
    """Weighted 0..1 score blending win rate, level, and sample size."""
    games = wins + losses
    adjusted_win_rate = (
        (wins + SHRINKAGE_GAMES * PRIOR_WIN_RATE)
        / (games + SHRINKAGE_GAMES)
    )
    games_confidence = min(games / FULL_CONFIDENCE_GAMES, 1.0)
    level_norm = min(avg_level / MAX_LEVEL, 1.0)
    return (
        WIN_RATE_WEIGHT * adjusted_win_rate
        + LEVEL_WEIGHT * level_norm
        + GAMES_WEIGHT * games_confidence
    )


def pick_recommended_decks(
    candidate_decks, owned_card_names, level_by_name,
    evolution_level_by_name, limit=3,
):
    """Score and rank candidate decks by playability for the owning player.

    `candidate_decks` is a list of dicts:
      {id, hash, count, wins, losses, card_ids: [...], evo_card_ids: [...],
       hero_card_ids: [...], cards: [{name, ...}]}
    where `cards` is the hydrated card list (already in render order).

    Returns the top `limit` decks ranked by:
       (1) fully playable (all required variants also unlocked) first,
       (2) then by a weighted score blending confidence-adjusted win rate,
           average card level, and games played (see _deck_score).

    Each result is the input dict augmented with:
      - avg_level, fully_playable, missing_variants, score
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
        score = _deck_score(
            avg_level, deck.get("wins", 0), deck.get("losses", 0)
        )
        annotated.append({
            **deck,
            "avg_level": round(avg_level, 1),
            "fully_playable": not missing,
            "missing_variants": missing,
            "score": round(score, 4),
        })
    annotated.sort(key=lambda d: (not d["fully_playable"], -d["score"]))
    return annotated[:limit]
