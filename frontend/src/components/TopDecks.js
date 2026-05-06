import React, { Component } from "react";
import Deck from "./Deck";
import DeckStats from "./DeckStats";
import {
    encodePlayerTag,
    getPlayerTag,
    subscribePlayerTag,
} from "../utils/playerTag";

const OVERLAY_KEY = "cr_stats_overlay_on";

function readOverlayPref(tag) {
    if (!tag) return false;
    const stored = localStorage.getItem(OVERLAY_KEY);
    if (stored === null) return true; // default ON when a tag is set
    return stored === "1";
}

function writeOverlayPref(on) {
    localStorage.setItem(OVERLAY_KEY, on ? "1" : "0");
}

export default class TopDecks extends Component {
    _fetchSeq = 0;

    state = {
        loading: true,
        top_decks: null,
        playerData: null,
        playerError: null,
        overlayOn: readOverlayPref(getPlayerTag()),
        tag: getPlayerTag(),
    };

    async componentDidMount() {
        this.unsubscribe = subscribePlayerTag(() => {
            const tag = getPlayerTag();
            this.setState(
                {
                    tag,
                    overlayOn: readOverlayPref(tag),
                    playerData: null,
                    playerError: null,
                },
                () => this.fetchPlayer()
            );
        });

        // Decks fetch and player fetch happen in parallel.
        const decksPromise = fetch("http://localhost:5001/decks").then((r) =>
            r.json()
        );
        const [decks] = await Promise.all([decksPromise, this.fetchPlayer()]);
        this.setState({ loading: false, top_decks: decks });
    }

    componentWillUnmount() {
        if (this.unsubscribe) this.unsubscribe();
    }

    async fetchPlayer() {
        const seq = ++this._fetchSeq;
        const tag = getPlayerTag();
        if (!tag) {
            this.setState({ playerData: null, playerError: null });
            return;
        }
        this.setState({ playerError: null });
        try {
            const res = await fetch(
                `http://localhost:5001/player/${encodePlayerTag(tag)}`
            );
            if (seq !== this._fetchSeq) return;
            if (res.status === 404) {
                this.setState({
                    playerData: null,
                    playerError: "not_found",
                });
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const playerData = await res.json();
            if (seq !== this._fetchSeq) return;
            this.setState({ playerData, playerError: null });
        } catch (err) {
            if (seq !== this._fetchSeq) return;
            this.setState({
                playerData: null,
                playerError: err.message,
            });
        }
    }

    toggleOverlay = () => {
        this.setState(
            (prev) => ({ overlayOn: !prev.overlayOn }),
            () => writeOverlayPref(this.state.overlayOn)
        );
    };

    buildOwnershipMap() {
        const { playerData } = this.state;
        if (!playerData) return null;
        const map = {};
        for (const c of playerData.cards) {
            map[c.name] = {
                level: c.level,
                evolutionLevel: c.evolutionLevel,
            };
        }
        return map;
    }

    renderControls() {
        const { tag, playerData, playerError, overlayOn } = this.state;
        if (!tag) return null;
        if (playerError === "not_found") {
            return (
                <div className="alert alert-warning py-2 mb-3">
                    Player tag <code>{tag}</code> not found — fix it in the navbar.
                </div>
            );
        }
        if (playerError) {
            return (
                <div className="alert alert-danger py-2 mb-3">
                    Couldn't load player data: {playerError}
                </div>
            );
        }
        if (!playerData) return null;
        return (
            <div className="form-check form-switch mb-3 text-white">
                <input
                    className="form-check-input"
                    type="checkbox"
                    role="switch"
                    id="overlayToggle"
                    checked={overlayOn}
                    onChange={this.toggleOverlay}
                />
                <label className="form-check-label" htmlFor="overlayToggle">
                    Show ownership overlay ({playerData.identity.name})
                </label>
            </div>
        );
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
        const ownership = this.state.overlayOn ? this.buildOwnershipMap() : null;
        return (
            <div>
                {this.renderControls()}
                {decks.map((deck, idx) => (
                    <div key={idx} className="mb-5 text-white">
                        <div className="mb-2">
                            <span className="fw-bold">Deck #{idx + 1}</span>
                            <span className="text-muted ms-2">
                                used by {deck.count} top{" "}
                                {deck.count === 1 ? "player" : "players"}
                            </span>
                        </div>
                        <div className="row">
                            <div className="col-md-9">
                                <Deck cards={deck.cards} ownership={ownership} />
                                <div className="text-muted small mt-2">
                                    {deck.players.join(", ")}
                                </div>
                            </div>
                            <div className="col-md-3">
                                <DeckStats cards={deck.cards} />
                            </div>
                        </div>
                        <hr className="mt-4" />
                    </div>
                ))}
            </div>
        );
    }
}
