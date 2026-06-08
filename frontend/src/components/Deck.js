import React from "react";
import { isVariantUnlocked } from "../utils/variants";

// Displayed in-game level cap; keep in sync with MAX_DISPLAYED_LEVEL in
// backend/apis/player.py. Max-level cards get a gold badge.
const MAX_LEVEL = 16;

// activeForm is set explicitly by the backend's hydrate_deck:
// "evolution" → use evolvedIcon, "hero" → use heroIcon,
// "champion" or null → use the regular icon (champion's regular icon
// is the champion-bordered version, no separate file).
function pickIcon({ icon, evolvedIcon, heroIcon, activeForm }) {
    if (activeForm === "evolution" && evolvedIcon) return evolvedIcon;
    if (activeForm === "hero" && heroIcon) return heroIcon;
    return icon;
}

function ownershipBadge(card, ownership) {
    if (!ownership) return null;
    const info = ownership[card.name];
    if (!info) {
        return (
            <span className="badge bg-danger position-absolute top-0 end-0 m-1">
                Missing
            </span>
        );
    }
    const variant = card.activeForm;
    // Champions don't have a separate unlock — owning the card is enough.
    if (variant && variant !== "champion"
        && !isVariantUnlocked(info.evolutionLevel, variant)) {
        return (
            <span className="badge bg-warning text-dark position-absolute top-0 end-0 m-1">
                no {variant === "hero" ? "hero" : "evo"}
            </span>
        );
    }
    const isMaxLevel = info.level >= MAX_LEVEL;
    return (
        <span
            className={`badge position-absolute top-0 end-0 m-1 ${
                isMaxLevel ? "text-dark" : "bg-dark"
            }`}
            style={isMaxLevel ? { backgroundColor: "#ffd700" } : undefined}
        >
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
                            src={pickIcon(card)}
                            alt={card.name}
                            className={`img-fluid${missing ? " opacity-25" : ""}`}
                            loading="lazy"
                            decoding="async"
                            onError={handleError}
                        />
                        {ownershipBadge(card, ownership)}
                    </div>
                );
            })}
        </div>
    );
}
