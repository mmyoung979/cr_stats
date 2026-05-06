EVO_BIT = 1
HERO_BIT = 2


def slot_active_variant(slot_idx, has_evolution, has_hero):
    """Which variant the deck slot is using. Returns 'evolution', 'hero', or None.

    Slot 0 is the evolution slot. Slot 1 is the hero slot (with evolution as a
    fallback). Slot 2 is hero or evolution (hero default when both unlocked).
    Slots 3-7 carry no variant.
    """
    if slot_idx == 0:
        return "evolution" if has_evolution else None
    if slot_idx in (1, 2):
        if has_hero:
            return "hero"
        if has_evolution:
            return "evolution"
    return None


def is_variant_unlocked(evolution_level, variant):
    """Bitmask check on `evolution_level`. None or 0 means nothing unlocked.

    `variant` is 'evolution', 'hero', or None. None always returns True.
    """
    if variant is None:
        return True
    bit = HERO_BIT if variant == "hero" else EVO_BIT
    return bool((evolution_level or 0) & bit)
