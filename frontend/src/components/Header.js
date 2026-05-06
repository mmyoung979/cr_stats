import React, { Component } from "react";
import { Link, NavLink } from "react-router";
import PlayerTagInput from "./PlayerTagInput";
import {
    encodePlayerTag,
    getPlayerTag,
    subscribePlayerTag,
} from "../utils/playerTag";

const navLinkClass = ({ isActive }) =>
    "nav-link" + (isActive ? " active" : "");

export default class Header extends Component {
    state = { tag: getPlayerTag() };

    componentDidMount() {
        this.unsubscribe = subscribePlayerTag(() =>
            this.setState({ tag: getPlayerTag() })
        );
    }

    componentWillUnmount() {
        if (this.unsubscribe) this.unsubscribe();
    }

    render() {
        const { tag } = this.state;
        return (
            <header>
                <link
                    href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.1/dist/css/bootstrap.min.css"
                    rel="stylesheet"
                    integrity="sha384-F3w7mX95PdgyTmZZMECAngseQB83DfGTowi0iMjiWaeVhAn4FJkqJByhZMI3AhiU"
                    crossOrigin="anonymous"
                />
                <nav className="navbar navbar-expand-md navbar-dark bg-dark">
                    <div className="container">
                        <Link to="/" className="navbar-brand">
                            Clash Royale Stats
                        </Link>
                        <button
                            className="navbar-toggler"
                            type="button"
                            data-bs-toggle="collapse"
                            data-bs-target="#cr-navmenu"
                            aria-controls="cr-navmenu"
                            aria-expanded="false"
                            aria-label="Toggle navigation"
                        >
                            <span className="navbar-toggler-icon"></span>
                        </button>
                        <div className="collapse navbar-collapse" id="cr-navmenu">
                            <ul className="navbar-nav me-auto">
                                <li className="nav-item">
                                    <NavLink to="/" end className={navLinkClass}>
                                        Cards
                                    </NavLink>
                                </li>
                                <li className="nav-item">
                                    <NavLink to="/decks" className={navLinkClass}>
                                        Decks
                                    </NavLink>
                                </li>
                                <li className="nav-item">
                                    <NavLink to="/battles" className={navLinkClass}>
                                        Battles
                                    </NavLink>
                                </li>
                                {tag && (
                                    <li className="nav-item">
                                        <NavLink
                                            to={`/player/${encodePlayerTag(tag)}`}
                                            className={navLinkClass}
                                        >
                                            My Profile
                                        </NavLink>
                                    </li>
                                )}
                            </ul>
                            <div className="d-flex">
                                <PlayerTagInput />
                            </div>
                        </div>
                    </div>
                </nav>
            </header>
        );
    }
}
