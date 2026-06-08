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

# Per-card level quality is NON-LINEAR: max level is ideal, max-1 is still
# competitive, max-2 is meaningfully underleveled, and it falls off fast below
# that. Applied per card (then averaged) so a single very-underleveled card
# isn't masked by an otherwise high average. Levels are integers; anything
# above the table is ideal, anything below is treated as ~0.
LEVEL_QUALITY = {
    16: 1.00,   # ideal
    15: 0.85,   # competitive
    14: 0.50,   # underleveled
    13: 0.20,
    12: 0.05,
}
MIN_LEVEL_QUALITY = 0.0


def _level_quality(level):
    if level >= MAX_LEVEL:
        return 1.0
    return LEVEL_QUALITY.get(level, MIN_LEVEL_QUALITY)


def _deck_score(card_levels, wins, losses):
    """Weighted 0..1 score blending win rate, level quality, and sample size.

    `card_levels` is the list of per-card displayed levels (integers); each is
    run through the non-linear LEVEL_QUALITY curve and averaged.
    """
    games = wins + losses
    adjusted_win_rate = (
        (wins + SHRINKAGE_GAMES * PRIOR_WIN_RATE)
        / (games + SHRINKAGE_GAMES)
    )
    games_confidence = min(games / FULL_CONFIDENCE_GAMES, 1.0)
    level_quality = (
        sum(_level_quality(lvl) for lvl in card_levels) / len(card_levels)
        if card_levels else 0.0
    )
    return (
        WIN_RATE_WEIGHT * adjusted_win_rate
        + LEVEL_WEIGHT * level_quality
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
        card_levels = [level_by_name[n] for n in names]
        avg_level = sum(card_levels) / len(card_levels)
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
            card_levels, deck.get("wins", 0), deck.get("losses", 0)
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
