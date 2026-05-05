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

    renderPlayerHeader(name, tag, rank, won, align) {
        return (
            <div className={`d-flex align-items-baseline mb-2 ${align === "right" ? "justify-content-end" : ""}`}>
                {align === "right" && won && (
                    <span className="badge bg-primary me-2">Victory</span>
                )}
                <div className={align === "right" ? "text-end" : ""}>
                    <div className="fw-bold">{name}</div>
                    {rank && <div className="small text-muted">Rank #{rank}</div>}
                    <div className="small text-muted">{tag}</div>
                </div>
                {align === "left" && won && (
                    <span className="badge bg-primary ms-2">Victory</span>
                )}
            </div>
        );
    }

    renderBattle(b) {
        const oppWins = b.opp_crowns > b.team_crowns;
        const draw = b.team_crowns === b.opp_crowns;
        const team = { name: b.team_name, tag: b.team_tag, rank: b.team_rank, deck: b.team_deck, crowns: b.team_crowns };
        const opp = { name: b.opp_name, tag: b.opp_tag, rank: null, deck: b.opp_deck, crowns: b.opp_crowns };
        const left = oppWins ? opp : team;
        const right = oppWins ? team : opp;
        const totalMin = Math.max(0, Math.floor((Date.now() - new Date(b.battle_time).getTime()) / 60000));
        const hours = Math.floor(totalMin / 60);
        const minutes = totalMin % 60;
        const when = hours === 0 ? `${minutes}m ago` : `${hours}h ${minutes}m ago`;
        return (
            <div key={`${b.battle_time}-${b.team_tag}`} className="battle-section mb-5 text-white">
                <div className="row align-items-start">
                    <div className="col-md-5">
                        {this.renderPlayerHeader(left.name, left.tag, left.rank, !draw, "left")}
                        {this.renderDeck(left.deck)}
                    </div>
                    <div className="col-md-2 text-center">
                        <div className="small text-muted mb-2">{when}</div>
                        <div className="fs-4 fw-bold">
                            {left.crowns} &ndash; {right.crowns}
                        </div>
                        {draw && <div className="small text-muted">Draw</div>}
                    </div>
                    <div className="col-md-5">
                        {this.renderPlayerHeader(right.name, right.tag, right.rank, false, "right")}
                        {this.renderDeck(right.deck)}
                    </div>
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
        return <div>{this.state.battles.map((b) => this.renderBattle(b))}</div>;
    }
}
