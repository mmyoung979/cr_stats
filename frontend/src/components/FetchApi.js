import React from "react";
import Card from "./Card";

const FetchApi = () => {
  const [state, setState] = React.useState({
    loading: true,
    top_cards: null,
  });

  React.useEffect(() => {
    const loadData = async () => {
      const url = "http://localhost:5000/";
      const response = await fetch(url);
      const data = await response.json();

      setState({
        loading: false,
        top_cards: data,
      });
    };

    if (state.loading) {
      loadData();
    }
  }, [state.loading]);

  return (
    <div className="row">
      {state.loading ? (
        <div className="text-center text-white">Loading API data...</div>
      ) : (
        state.top_cards
          .sort((a, b) => {
            return b.count - a.count;
          })
          .map((card, index) => {
            return (
              <div
                key={card.name}
                className="col-lg-3 col-sm-6 col-sm-offset-3"
              >
                <Card
                  icon={card.icon}
                  name={card.name}
                  count={card.count}
                  rank={index + 1}
                />
              </div>
            );
          })
      )}
    </div>
  );
};

export default FetchApi;
