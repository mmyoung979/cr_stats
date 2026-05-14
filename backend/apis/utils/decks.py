def _card_json(card_row, active_form):
    return {
        "name": card_row["name"],
        "icon": card_row["icon_url"],
        "evolvedIcon": card_row["evolution_icon_url"],
        "heroIcon": card_row["hero_icon_url"],
        "hasEvolution": card_row["has_evolution"],
        "hasHero": card_row["has_hero"],
        "elixirCost": card_row["elixir_cost"],
        "activeForm": active_form,
    }


def hydrate_deck(deck_row, cards_by_id):
    """Build the frontend per-card JSON list for one deck.

    Slots 0/1/2 are the variant slots, filled in priority order to mirror
    the CR client layout:
      - Slot 0: evo (if any), else regular
      - Slot 1: hero (if any), else evo (fallback), else regular
      - Slot 2: hero (if any remaining), else evo (fallback), else regular
    Slots 3-7: remaining regular cards, sorted by elixir cost ascending.
    activeForm derived from membership in evo_card_ids / hero_card_ids.
    Unknown card_ids are skipped.
    """
    evos = list(deck_row["evo_card_ids"])
    heroes = list(deck_row["hero_card_ids"])
    variant_set = set(evos) | set(heroes)

    # Sort regular (non-variant) cards by elixir cost ascending so any
    # regular that fills a leftover variant slot is the cheapest available.
    other_rows = [
        cards_by_id[cid]
        for cid in deck_row["card_ids"]
        if cid not in variant_set and cid in cards_by_id
    ]
    other_rows.sort(key=lambda r: r["elixir_cost"] if r["elixir_cost"] is not None else 0)
    other_ids = [r["id"] for r in other_rows]

    def take_slot_0():
        if evos:
            return (evos.pop(0), "evolution")
        if other_ids:
            return (other_ids.pop(0), None)
        return None

    def take_hero_or_evo_slot():
        if heroes:
            return (heroes.pop(0), "hero")
        if evos:
            return (evos.pop(0), "evolution")
        if other_ids:
            return (other_ids.pop(0), None)
        return None

    head = []
    for picker in (take_slot_0, take_hero_or_evo_slot, take_hero_or_evo_slot):
        slot = picker()
        if slot is not None:
            head.append(slot)

    result = []
    for cid, active_form in head:
        row = cards_by_id.get(cid)
        if row is None:
            continue
        result.append(_card_json(row, active_form))
    for cid in other_ids:
        row = cards_by_id.get(cid)
        if row is not None:
            result.append(_card_json(row, None))

    return result
