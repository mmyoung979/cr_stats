import React, { Component } from "react";
import BattleCard from "./BattleCard";

export default class Battles extends Component {
    state = {
        loading: true,
        battles: null,
        error: null,
    };

    async componentDidMount() {
        try {
            const res = await fetch("http://localhost:5001/battles");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const battles = await res.json();
            this.setState({ loading: false, battles });
        } catch (err) {
            this.setState({ loading: false, error: err.message });
        }
    }

    renderDeck(deck) {
        return (
            <div className="row">
                {deck.map((card, idx) => (
                    <div key={idx} className="col-3">
                        <BattleCard
                            name={card.name}
                            icon={card.icon}
                            evolvedIcon={card.evolvedIcon}
                            hasEvolution={card.hasEvolution}
                            isEvolutionSlot={idx < 2}
                        />
                    </div>
                ))}
            </div>
        );
    }

    renderBattle(b, idx) {
        const teamWins = b.team_crowns > b.opp_crowns;
        const oppWins = b.opp_crowns > b.team_crowns;
        const draw = !teamWins && !oppWins;
        const when = new Date(b.battle_time).toUTCString();
        return (
            <div key={`${b.battle_time}-${b.team_tag}`} className="battle-section mb-4 text-white">
                <div className="battle-title mb-2">
                    Battle #{idx + 1} &mdash; {when}
                </div>
                <div className="battle-header mb-2">
                    <span>
                        {b.team_name} ({b.team_tag}){teamWins ? " — WINNER" : ""}
                    </span>
                    <span className="mx-3">
                        {b.team_crowns} – {b.opp_crowns}
                        {draw ? " (Draw)" : ""}
                    </span>
                    <span>
                        {b.opp_name} ({b.opp_tag}){oppWins ? " — WINNER" : ""}
                    </span>
                </div>
                <div className="row">
                    <div className="col-md-6">{this.renderDeck(b.team_deck)}</div>
                    <div className="col-md-6">{this.renderDeck(b.opp_deck)}</div>
                </div>
                <hr />
            </div>
        );
    }

    render() {
        if (this.state.loading) {
            return <div className="text-center text-white">Loading API data...</div>;
        }
        if (this.state.error) {
            return (
                <div className="text-center text-white">
                    Failed to load battles: {this.state.error}
                </div>
            );
        }
        return <div>{this.state.battles.map((b, i) => this.renderBattle(b, i))}</div>;
    }
}
