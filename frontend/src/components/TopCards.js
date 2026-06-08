import React, { Component } from "react";
import Card from "./Card";

const TYPES = ["building", "spell", "troop"];
const RARITIES = ["common", "rare", "epic", "legendary", "champion"];

const titleCase = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export default class TopCards extends Component {
    state = {
        loading: true,
        top_cards: null,
        typeFilter: "all",
        rarityFilter: "all",
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

    renderFilters() {
        const { typeFilter, rarityFilter } = this.state;
        return (
            <div className="col-12 d-flex flex-wrap gap-3 mb-2">
                <div>
                    <label className="form-label text-white small mb-1">
                        Type
                    </label>
                    <select
                        className="form-select form-select-sm"
                        value={typeFilter}
                        onChange={(e) =>
                            this.setState({ typeFilter: e.target.value })
                        }
                    >
                        <option value="all">All types</option>
                        {TYPES.map((t) => (
                            <option key={t} value={t}>
                                {titleCase(t)}
                            </option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="form-label text-white small mb-1">
                        Rarity
                    </label>
                    <select
                        className="form-select form-select-sm"
                        value={rarityFilter}
                        onChange={(e) =>
                            this.setState({ rarityFilter: e.target.value })
                        }
                    >
                        <option value="all">All rarities</option>
                        {RARITIES.map((r) => (
                            <option key={r} value={r}>
                                {titleCase(r)}
                            </option>
                        ))}
                    </select>
                </div>
            </div>
        );
    }

    render() {
        const { loading, top_cards, typeFilter, rarityFilter } = this.state;
        if (loading) {
            return (
                <div className="text-center text-white">Loading API data...</div>
            );
        }

        const cards = top_cards
            .filter(
                (card) => typeFilter === "all" || card.type === typeFilter
            )
            .filter(
                (card) =>
                    rarityFilter === "all" || card.rarity === rarityFilter
            )
            .sort((a, b) => b.count - a.count);

        return (
            <div className="row gy-4">
                {this.renderFilters()}
                {cards.length === 0 ? (
                    <div className="text-center text-white">
                        No cards match these filters.
                    </div>
                ) : (
                    cards.map((card, index) => (
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
                    ))
                )}
            </div>
        );
    }
}
