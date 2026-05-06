import React from "react";
import { activeSlotVariant, isVariantUnlocked } from "../utils/variants";

// Per-slot variant rule:
// slot 0 = evolution slot, slot 1 = hero (evo as fallback for malformed
// decks), slot 2 = hero or evo (hero default when both unlocked), else regular.
function pickIcon({ slotIndex, icon, evolvedIcon, heroIcon, hasEvolution, hasHero }) {
    if (slotIndex === 0) {
        return hasEvolution && evolvedIcon ? evolvedIcon : icon;
    }
    if (slotIndex === 1 || slotIndex === 2) {
        if (hasHero && heroIcon) return heroIcon;
        if (hasEvolution && evolvedIcon) return evolvedIcon;
    }
    return icon;
}

function ownershipBadge(card, slotIndex, ownership) {
    if (!ownership) return null;
    const info = ownership[card.name];
    if (!info) {
        return (
            <span className="badge bg-danger position-absolute top-0 end-0 m-1">
                Missing
            </span>
        );
    }
    const variant = activeSlotVariant(slotIndex, card.hasEvolution, card.hasHero);
    if (variant && !isVariantUnlocked(info.evolutionLevel, variant)) {
        return (
            <span className="badge bg-warning text-dark position-absolute top-0 end-0 m-1">
                no {variant === "hero" ? "hero" : "evo"}
            </span>
        );
    }
    return (
        <span className="badge bg-dark position-absolute top-0 end-0 m-1">
            {info.level}
        </span>
    );
}

export default function Deck({ cards, ownership }) {
    return (
        <div className="row g-2">
            {cards.map((card, idx) => {
                const handleError = (e) => {
                    if (e.target.src !== card.icon) {
                        e.target.src = card.icon;
                    }
                };
                const missing = ownership && !ownership[card.name];
                return (
                    <div key={idx} className="col-3 position-relative">
                        <img
                            src={pickIcon({ ...card, slotIndex: idx })}
                            alt={card.name}
                            className={`img-fluid${missing ? " opacity-25" : ""}`}
                            loading="lazy"
                            decoding="async"
                            onError={handleError}
                        />
                        {ownershipBadge(card, idx, ownership)}
                    </div>
                );
            })}
        </div>
    );
}
