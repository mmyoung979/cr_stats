def _card_json(card_row, active_form):
    return {
        "name": card_row["name"],
        "icon": card_row["icon_url"],
        "evolvedIcon": card_row["evolution_icon_url"],
        "heroIcon": card_row["hero_icon_url"],
        "hasEvolution": card_row["has_evolution"],
        "hasHero": card_row["has_hero"],
        "elixir_cost": card_row["elixir_cost"],
        "activeForm": active_form,
    }


def hydrate_deck(deck_row, cards_by_id):
    """Build the frontend per-card JSON list for one deck.

    Order: evos first, then heroes, then regulars — each group sorted by
    elixir_cost ascending. activeForm is derived from membership in the
    deck's evo_card_ids / hero_card_ids. Unknown card_ids are skipped.
    """
    evo_set = set(deck_row["evo_card_ids"])
    hero_set = set(deck_row["hero_card_ids"])

    evos, heroes, regulars = [], [], []
    for card_id in deck_row["card_ids"]:
        card_row = cards_by_id.get(card_id)
        if card_row is None:
            continue
        if card_id in evo_set:
            evos.append(_card_json(card_row, "evolution"))
        elif card_id in hero_set:
            heroes.append(_card_json(card_row, "hero"))
        else:
            regulars.append(_card_json(card_row, None))

    def by_elixir(card):
        return card["elixir_cost"] if card["elixir_cost"] is not None else 0

    evos.sort(key=by_elixir)
    heroes.sort(key=by_elixir)
    regulars.sort(key=by_elixir)
    return evos + heroes + regulars
