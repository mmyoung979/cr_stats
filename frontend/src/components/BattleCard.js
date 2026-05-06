import React from "react";

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

export default function BattleCard(props) {
    const handleError = (e) => {
        if (e.target.src !== props.icon) {
            e.target.src = props.icon;
        }
    };
    return (
        <img
            src={pickIcon(props)}
            alt={props.name}
            className="img-fluid my-2"
            loading="lazy"
            decoding="async"
            onError={handleError}
        />
    );
}
