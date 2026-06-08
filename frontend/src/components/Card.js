import React, { Component } from "react";

export default class Card extends Component {
    render() {
        const { name, rank, count } = this.props;
        const heroShare = count ? this.props.heroCount / count : 0;
        const evoShare = count ? this.props.evolutionCount / count : 0;

        let icon = this.props.icon;
        if (this.props.hasHero && this.props.heroIcon && heroShare >= 0.5) {
            icon = this.props.heroIcon;
        } else if (this.props.hasEvolution && this.props.evolvedIcon && evoShare >= 0.5) {
            icon = this.props.evolvedIcon;
        }

        return (
            <div className="card h-100">
                <div className="position-relative">
                    <img
                        src={icon}
                        className="card-img-top py-3"
                        alt={name}
                        loading="lazy"
                        decoding="async"
                        onError={(e) => {
                            if (e.target.src !== this.props.icon) {
                                e.target.src = this.props.icon;
                            }
                        }}
                    />
                    <span className="badge bg-primary position-absolute top-0 start-0 m-2">
                        #{rank}
                    </span>
                </div>
                <div className="card-body">
                    <h5 className="card-title">{name}</h5>
                    <p className="card-text">
                        <b>{count}</b>/1000 top players use {name}
                    </p>
                    {count > 0 && this.props.hasHero && (
                        <p className="card-text">
                            <b>{this.props.heroCount}/{count}</b> use the hero variant.
                        </p>
                    )}
                    {count > 0 && this.props.hasEvolution && (
                        <p className="card-text">
                            <b>{this.props.evolutionCount}/{count}</b> are evolved.
                        </p>
                    )}
                    {!this.props.hasHero && !this.props.hasEvolution && (
                        <p className="card-text">
                            <b>No evolution</b>
                        </p>
                    )}
                </div>
            </div>
        );
    }
}
