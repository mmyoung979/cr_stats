import React, { Component } from "react";
import Card from "./Card";

export default class TopCards extends Component {
    state = {
        loading: true,
        top_cards: null,
    };

    async componentDidMount() {
        const url = "http://localhost:5001/cards";
        const response = await fetch(url);
        const data = await response.json();
        this.setState({
            top_cards: data,
            loading: false,
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
                    this.state.top_cards
                        .sort((a, b) => b.count - a.count)
                        .map((card, index) => {
                            return (
                                <div
                                    key={card.name}
                                    className="col-lg-2 col-sm-6 col-sm-offset-3"
                                >
                                    <Card
                                        icon={card.icon}
                                        evolvedIcon={card.evolvedIcon}
                                        heroIcon={card.heroIcon}
                                        name={card.name}
                                        count={card.count}
                                        evolutionCount={card.evolutionCount}
                                        heroCount={card.heroCount}
                                        hasEvolution={card.hasEvolution}
                                        hasHero={card.hasHero}
                                        rank={index + 1}
                                    />
                                </div>
                            );
                        })
                )}
            </div>
        );
    }
}
