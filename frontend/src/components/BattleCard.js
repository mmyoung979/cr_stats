import React from "react";

export default function BattleCard({ name, icon, evolvedIcon, hasEvolution, isEvolutionSlot }) {
    const showEvolved = isEvolutionSlot && hasEvolution && evolvedIcon;
    return (
        <div className="card my-2">
            <img
                src={showEvolved ? evolvedIcon : icon}
                className="card-img-top py-2"
                alt={name}
            />
            <div className="card-body p-2">
                <h6 className="card-title mb-0">{name}</h6>
            </div>
        </div>
    );
}
