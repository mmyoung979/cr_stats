def pick_recommended_decks(all_decks, owned_card_names, level_by_name, limit=3):
    """Return the top `limit` decks the player can fully play, ranked by popularity.

    A deck is "playable" iff every card in it is in `owned_card_names`. Each
    returned deck is the original dict augmented with `avg_level` (mean of
    `level_by_name[name]` across the deck's cards, rounded to 1 decimal).
    Sort is stable on `count` descending — ties preserve input order.
    """
    playable = []
    for deck in all_decks:
        names = [c["name"] for c in deck["cards"]]
        if not all(n in owned_card_names for n in names):
            continue
        avg_level = sum(level_by_name[n] for n in names) / len(names)
        playable.append({**deck, "avg_level": round(avg_level, 1)})
    playable.sort(key=lambda d: d["count"], reverse=True)
    return playable[:limit]
