import React, { Component } from "react";
import Header from "./components/Header";
import "./App.css";
import "./components/TopCards";

const root = document.getElementById("root");

export default class App extends Component {
    render() {
        return (
            <div className="App">
                <Header />
                <div className="container mt-3">
                    {this.props.component &&
                        React.createElement(this.props.component)}
                </div>
                <script
                    src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.1/dist/js/bootstrap.bundle.min.js"
                    integrity="sha384-/bQdsTh/da6pkI1MST/rWKFNjaCP5gBSY4sEBT38Q/9RBh9AH40zEOg7Hlq2THRZ"
                    crossOrigin="anonymous"
                ></script>
            </div>
        );
    }
}
