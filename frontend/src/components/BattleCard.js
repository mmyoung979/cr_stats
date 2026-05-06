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
    return (
        <div className="card my-2">
            <img
                src={pickIcon(props)}
                className="card-img-top py-2"
                alt={props.name}
                loading="lazy"
                decoding="async"
                width="285"
                height="420"
            />
            <div className="card-body p-2">
                <h6 className="card-title mb-0">{props.name}</h6>
            </div>
        </div>
    );
}
