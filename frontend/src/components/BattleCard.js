import React from "react";

export default function BattleCard({
    name,
    icon,
    evolvedIcon,
    heroIcon,
    hasEvolution,
    hasHero,
    isSpecialSlot,
}) {
    let displayIcon = icon;
    if (isSpecialSlot && hasHero && heroIcon) {
        displayIcon = heroIcon;
    } else if (isSpecialSlot && hasEvolution && evolvedIcon) {
        displayIcon = evolvedIcon;
    }
    return (
        <div className="card my-2">
            <img
                src={displayIcon}
                className="card-img-top py-2"
                alt={name}
            />
            <div className="card-body p-2">
                <h6 className="card-title mb-0">{name}</h6>
            </div>
        </div>
    );
}
