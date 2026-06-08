import React, { Component } from "react";
import Deck from "./Deck";
import DeckStats from "./DeckStats";
import { avgElixir, fourCardCycle, gamesPlayed } from "../utils/deckMetrics";
import {
    encodePlayerTag,
    getPlayerTag,
    subscribePlayerTag,
} from "../utils/playerTag";

const OVERLAY_KEY = "cr_stats_overlay_on";

// Sort options for the decks page. Each accessor returns a number or null;
// nulls always sort last regardless of direction.
const SORT_OPTIONS = [
    { key: "players", label: "Players", get: (d) => d.count },
    { key: "winRate", label: "Win rate", get: (d) => d.winRate },
    { key: "games", label: "Games played", get: (d) => gamesPlayed(d) },
    { key: "elixir", label: "Avg elixir", get: (d) => avgElixir(d.cards) },
    { key: "cycle", label: "4-card cycle", get: (d) => fourCardCycle(d.cards) },
];

function sortDecks(decks, sortKey, sortDir) {
    const opt = SORT_OPTIONS.find((o) => o.key === sortKey) || SORT_OPTIONS[0];
    const mul = sortDir === "asc" ? 1 : -1;
    return [...decks].sort((a, b) => {
        const av = opt.get(a);
        const bv = opt.get(b);
        if (av == null && bv == null) return 0;
        if (av == null) return 1; // nulls last
        if (bv == null) return -1;
        return (av - bv) * mul;
    });
}

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
        sortKey: "players",
        sortDir: "desc",
        playableOnly: false,
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

    renderSortControls(canFilterPlayable) {
        const { sortKey, sortDir, playableOnly } = this.state;
        return (
            <div className="d-flex flex-wrap align-items-end gap-3 mb-3">
                <div>
                    <label className="form-label text-white small mb-1">
                        Sort by
                    </label>
                    <select
                        className="form-select form-select-sm"
                        value={sortKey}
                        onChange={(e) =>
                            this.setState({ sortKey: e.target.value })
                        }
                    >
                        {SORT_OPTIONS.map((o) => (
                            <option key={o.key} value={o.key}>
                                {o.label}
                            </option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="form-label text-white small mb-1">
                        Order
                    </label>
                    <select
                        className="form-select form-select-sm"
                        value={sortDir}
                        onChange={(e) =>
                            this.setState({ sortDir: e.target.value })
                        }
                    >
                        <option value="desc">Descending</option>
                        <option value="asc">Ascending</option>
                    </select>
                </div>
                <div className="form-check text-white pb-1">
                    <input
                        className="form-check-input"
                        type="checkbox"
                        id="playableOnly"
                        checked={playableOnly}
                        disabled={!canFilterPlayable}
                        onChange={(e) =>
                            this.setState({ playableOnly: e.target.checked })
                        }
                    />
                    <label
                        className="form-check-label"
                        htmlFor="playableOnly"
                    >
                        Only playable decks
                        {!canFilterPlayable && (
                            <span className="text-muted ms-1">
                                (set a player tag)
                            </span>
                        )}
                    </label>
                </div>
            </div>
        );
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
        const { sortKey, sortDir, playableOnly } = this.state;
        const ownedMap = this.buildOwnershipMap();
        const ownership = this.state.overlayOn ? ownedMap : null;

        let decks = this.state.top_decks;
        if (playableOnly && ownedMap) {
            decks = decks.filter((d) =>
                d.cards.every((c) => ownedMap[c.name])
            );
        }
        decks = sortDecks(decks, sortKey, sortDir);

        return (
            <div>
                {this.renderSortControls(!!ownedMap)}
                {this.renderControls()}
                {decks.length === 0 ? (
                    <div className="text-white">No decks match these filters.</div>
                ) : (
                decks.map((deck, idx) => (
                    <div key={idx} className="mb-5 text-white">
                        <div className="mb-2">
                            <span className="fw-bold">Deck #{idx + 1}</span>
                            <span className="text-muted ms-2">
                                used by {deck.count} top{" "}
                                {deck.count === 1 ? "player" : "players"}
                            </span>
                            {deck.winRate != null && (
                                <span className="text-muted ms-2">
                                    · {deck.wins}W&ndash;{deck.losses}L (
                                    {deck.winRate}% win)
                                </span>
                            )}
                        </div>
                        <div className="row">
                            <div className="col-md-9">
                                <Deck cards={deck.cards} ownership={ownership} />
                                <details className="mt-2">
                                    <summary className="text-muted small">
                                        Players ({deck.players.length})
                                    </summary>
                                    <div className="text-muted small mt-1">
                                        {deck.players.join(", ")}
                                    </div>
                                </details>
                            </div>
                            <div className="col-md-3">
                                <DeckStats cards={deck.cards} />
                            </div>
                        </div>
                        <hr className="mt-4" />
                    </div>
                )))}
            </div>
        );
    }
}
