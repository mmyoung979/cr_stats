import React, { Component } from "react";
import Deck from "./Deck";

export default class TopDecks extends Component {
    state = {
        loading: true,
        top_decks: null,
    };

    async componentDidMount() {
        const url = "http://localhost:5001/decks";
        const response = await fetch(url);
        const data = await response.json();
        this.setState({
            loading: false,
            top_decks: data,
        });
    }

    render() {
        if (this.state.loading) {
            return (
                <div className="text-center text-white">Loading API data...</div>
            );
        }
        const decks = [...this.state.top_decks].sort(
            (a, b) => b.count - a.count
        );
        return (
            <div>
                {decks.map((deck, idx) => (
                    <div key={idx} className="mb-5 text-white">
                        <div className="mb-2">
                            <span className="fw-bold">Deck #{idx + 1}</span>
                            <span className="text-muted ms-2">
                                used by {deck.count} top{" "}
                                {deck.count === 1 ? "player" : "players"}
                            </span>
                        </div>
                        <Deck cards={deck.cards} />
                        <div className="text-muted small mt-2">
                            {deck.players.join(", ")}
                        </div>
                        <hr className="mt-4" />
                    </div>
                ))}
            </div>
        );
    }
}
