import React from "react";

function avgElixir(cards) {
    const costs = cards.map((c) => c.elixirCost).filter((x) => typeof x === "number");
    if (costs.length === 0) return null;
    return (costs.reduce((a, b) => a + b, 0) / costs.length).toFixed(1);
}

function fourCardCycle(cards) {
    const costs = cards.map((c) => c.elixirCost).filter((x) => typeof x === "number");
    if (costs.length < 4) return null;
    const cheapest = [...costs].sort((a, b) => a - b).slice(0, 4);
    return cheapest.reduce((a, b) => a + b, 0).toFixed(1);
}

export default function DeckStats({ cards }) {
    const avg = avgElixir(cards);
    const cycle = fourCardCycle(cards);
    return (
        <div className="text-white">
            <div>Avg elixir: {avg ?? "—"}</div>
            <div>4-card cycle: {cycle ?? "—"}</div>
        </div>
    );
}
