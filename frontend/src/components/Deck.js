import React from "react";

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

export default function Deck({ cards }) {
    return (
        <div className="row g-2">
            {cards.map((card, idx) => {
                const handleError = (e) => {
                    if (e.target.src !== card.icon) {
                        e.target.src = card.icon;
                    }
                };
                return (
                    <div key={idx} className="col-3">
                        <img
                            src={pickIcon({ ...card, slotIndex: idx })}
                            alt={card.name}
                            className="img-fluid"
                            loading="lazy"
                            decoding="async"
                            onError={handleError}
                        />
                    </div>
                );
            })}
        </div>
    );
}
