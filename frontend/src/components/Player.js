import React, { Component } from "react";
import { useParams } from "react-router";
import Deck from "./Deck";
import { encodePlayerTag } from "../utils/playerTag";

function withParams(Component) {
    return function Wrapped(props) {
        const params = useParams();
        return <Component {...props} params={params} />;
    };
}

class Player extends Component {
    state = { loading: true, data: null, error: null, notFound: false };

    componentDidMount() {
        this.load();
    }

    componentDidUpdate(prev) {
        if (prev.params.tag !== this.props.params.tag) {
            this.setState({ loading: true, data: null, error: null, notFound: false });
            this.load();
        }
    }

    async load() {
        const { tag } = this.props.params;
        try {
            const res = await fetch(
                `http://localhost:5001/player/${encodePlayerTag(tag)}`
            );
            if (res.status === 404) {
                this.setState({ loading: false, notFound: true });
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this.setState({ loading: false, data });
        } catch (err) {
            this.setState({ loading: false, error: err.message });
        }
    }

    render() {
        const { loading, data, error, notFound } = this.state;
        if (loading) {
            return <div className="text-center text-white">Loading API data...</div>;
        }
        if (notFound) {
            return (
                <div className="text-center text-white">
                    Player not found — check the tag.
                </div>
            );
        }
        if (error) {
            return (
                <div className="text-center text-white">
                    Couldn't load player data: {error}
                </div>
            );
        }
        const { identity, recommended_decks } = data;
        return (
            <div className="text-white">
                <div className="mb-4">
                    <h2 className="mb-1">{identity.name}</h2>
                    <div className="text-muted">{identity.tag}</div>
                    <div className="mt-2">Trophies: {identity.trophies}</div>
                    {identity.pol_rank != null && (
                        <div>Path of Legend Rank: #{identity.pol_rank}</div>
                    )}
                </div>
                <h4 className="mb-3">Recommended Decks</h4>
                {recommended_decks.length === 0 ? (
                    <div className="text-muted">
                        No full meta deck matches your collection yet.
                    </div>
                ) : (
                    recommended_decks.map((deck, idx) => (
                        <div key={idx} className="mb-5">
                            <div className="mb-2">
                                <span className="fw-bold">Deck #{idx + 1}</span>
                                <span className="text-muted ms-2">
                                    used by {deck.count} top{" "}
                                    {deck.count === 1 ? "player" : "players"}
                                </span>
                                <span className="text-muted ms-2">
                                    · avg level {deck.avg_level}
                                </span>
                            </div>
                            {deck.missing_variants.length > 0 && (
                                <div className="small text-warning mb-2">
                                    Missing:{" "}
                                    {deck.missing_variants
                                        .map((m) => `${m.variant === "hero" ? "hero" : "evo"} ${m.name}`)
                                        .join(", ")}
                                </div>
                            )}
                            <Deck cards={deck.cards} />
                            <hr className="mt-4" />
                        </div>
                    ))
                )}
            </div>
        );
    }
}

export default withParams(Player);
