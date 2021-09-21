import React, { Component } from 'react';

export default class Card extends Component {
    render() {
        return (
            <div className="card my-3">
                <img src={this.props.icon} className="card-img-top py-3" alt={this.props.name} />
                <div className="card-body">
                    <h5 className="card-title">{this.props.name} (#{this.props.rank})</h5>
                    <p className="card-text"><b class>{this.props.count}</b>/50 top players use {this.props.name}</p>
                </div>
            </div>
        )
    }
}
