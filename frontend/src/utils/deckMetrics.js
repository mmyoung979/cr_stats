// Shared deck metric helpers, used both for display (DeckStats) and for
// sorting/filtering on the decks page. Each returns a raw number (or null
// when it can't be computed) — formatting is the caller's job.

function numericCosts(cards) {
    return cards.map((c) => c.elixirCost).filter((x) => typeof x === "number");
}

export function avgElixir(cards) {
    const costs = numericCosts(cards);
    if (costs.length === 0) return null;
    return costs.reduce((a, b) => a + b, 0) / costs.length;
}

export function fourCardCycle(cards) {
    const costs = numericCosts(cards);
    if (costs.length < 4) return null;
    const cheapest = [...costs].sort((a, b) => a - b).slice(0, 4);
    return cheapest.reduce((a, b) => a + b, 0);
}

export function gamesPlayed(deck) {
    return (deck.wins || 0) + (deck.losses || 0);
}
