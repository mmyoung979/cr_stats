import React, { Component } from "react";

export default class Card extends Component {
    render() {
        var icon = this.props.icon;
        if (
            this.props.hasEvolution &&
            this.props.evolutionCount / this.props.count >= 0.5
        ) {
            icon = this.props.evolvedIcon;
        }
        return (
            <div className="card my-3">
                <img
                    src={icon}
                    className="card-img-top py-3"
                    alt={this.props.name}
                />
                <div className="card-body">
                    <h5 className="card-title">
                        {this.props.name} (#{this.props.rank})
                    </h5>
                    <p className="card-text">
                        <b class>{this.props.count}</b>/100 top players use{" "}
                        {this.props.name}
                    </p>
                    {this.props.hasEvolution ? (
                        <p className="card-text">
                            <b>
                                {this.props.evolutionCount}/{this.props.count}
                            </b>{" "}
                            are evolved.
                        </p>
                    ) : (
                        <p className="card-text">
                            <b>No evolution</b>
                        </p>
                    )}
                </div>
            </div>
        );
    }
}
