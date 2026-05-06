// Per-slot variant rule mirrored from backend/apis/utils/variants.py.
// Slot 0 = evo slot. Slot 1 = hero (evo fallback). Slot 2 = hero (evo fallback).
// Slots 3-7 carry no variant.

const EVO_BIT = 1;
const HERO_BIT = 2;

export function activeSlotVariant(slotIndex, hasEvolution, hasHero) {
    if (slotIndex === 0) return hasEvolution ? "evolution" : null;
    if (slotIndex === 1 || slotIndex === 2) {
        if (hasHero) return "hero";
        if (hasEvolution) return "evolution";
    }
    return null;
}

export function isVariantUnlocked(evolutionLevel, variant) {
    if (!variant) return true;
    const bit = variant === "hero" ? HERO_BIT : EVO_BIT;
    return ((evolutionLevel || 0) & bit) !== 0;
}
