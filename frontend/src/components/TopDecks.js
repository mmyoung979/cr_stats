import React, { Component } from "react";
import Card from "./Card";

export default class TopDecks extends Component {
    state = {
        loading: true,
        top_cards: null,
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
        return (
            <div className="row">
                {this.state.loading ? (
                    <div className="text-center text-white">
                        Loading API data...
                    </div>
                ) : (
                    this.state.top_decks
                        .sort((a, b) => b.count - a.count)
                        .map((deck, deckIndex) => (
                            <div key={deckIndex} className="deck-section mb-4">
                                <div className="deck-title text-white mb-2">
                                    Deck #{deckIndex + 1} (Count: {deck.count})
                                </div>
                                <div className="deck-players text-white mb-2">
                                    <strong>Players:</strong>{" "}
                                    {deck.players.join(", ")}
                                </div>
                                <div className="row">
                                    {deck.cards.map((card, cardIndex) => (
                                        <div
                                            key={`${deckIndex}-${cardIndex}`}
                                            className="col-lg-3 col-sm-3 col-sm-offset-3"
                                        >
                                            <Card
                                                icon={card.icon}
                                                evolvedIcon={card.evolvedIcon}
                                                name={card.name}
                                                count={deck.count}
                                                evolutionCount={
                                                    [0, 1].includes(cardIndex)
                                                        ? deck.count
                                                        : 0
                                                }
                                                hasEvolution={card.hasEvolution}
                                                rank={deckIndex + 1}
                                            />
                                        </div>
                                    ))}
                                </div>
                                <hr className="deck-separator" />
                            </div>
                        ))
                )}
            </div>
        );
    }
}
