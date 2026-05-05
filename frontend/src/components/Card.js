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
            <div className="card my-3">
                <img src={icon} className="card-img-top py-3" alt={name} />
                <div className="card-body">
                    <h5 className="card-title">
                        {name} (#{rank})
                    </h5>
                    <p className="card-text">
                        <b>{count}</b>/100 top players use {name}
                    </p>
                    {this.props.hasHero && (
                        <p className="card-text">
                            <b>{this.props.heroCount}/{count}</b> use the hero variant.
                        </p>
                    )}
                    {this.props.hasEvolution && (
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
