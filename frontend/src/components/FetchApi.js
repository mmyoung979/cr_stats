import React, { Component } from 'react';
import Card from './Card';

export default class FetchApi extends Component {
    state = {
        loading: true,
        top_cards: null,
    };

    async componentDidMount() {
        const url = "http://localhost:5000/";
        const response = await fetch(url);
        const data = await response.json()
        this.setState({
            loading: false,
            top_cards: data
        });
    }

    render() {
        return (
            <div>
                {this.state.loading
                    ? <div className="text-center text-white">Loading API data...</div>
                    : this.state.top_cards
                        .sort((a, b) => { return b.count - a.count })
                        .map((card, index) => {
                            return <div key={card.name}>
                                <Card icon={card.icon} name={card.name} count={card.count} rank={index + 1} />
                            </div>
                        })
                }
            </div>
        )
    }
}
