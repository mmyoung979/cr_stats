import React from "react";
import { avgElixir, fourCardCycle } from "../utils/deckMetrics";

export default function DeckStats({ cards }) {
    const avg = avgElixir(cards);
    const cycle = fourCardCycle(cards);
    return (
        <div className="text-white">
            <div>Avg elixir: {avg != null ? avg.toFixed(1) : "—"}</div>
            <div>4-card cycle: {cycle ?? "—"}</div>
        </div>
    );
}
