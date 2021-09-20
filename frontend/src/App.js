import './App.css';
import './components/FetchApi';
import Header from './components/Header';
import FetchApi from './components/FetchApi';

function App() {
  return (
    <div className="App">
      <Header />
      <div className="container mt-3">
        <h1 className="h1 text-center">Clash Royale Stats</h1>
        <p className="text-center text-white">Scroll down to find the most commonly used cards among the top 50 players in Clash Royale.</p>
        <hr />
        <p className="text-center text-white">Designed by <a href="https://tiktok.com/@matthewmyoung" target="_blank" rel="noreferrer">@matthewmyoung</a> on TikTok</p>
        <div className="row">
          <div className="col-lg-6 offset-lg-3 col-sm-12">
            <FetchApi />
          </div>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.1/dist/js/bootstrap.bundle.min.js" integrity="sha384-/bQdsTh/da6pkI1MST/rWKFNjaCP5gBSY4sEBT38Q/9RBh9AH40zEOg7Hlq2THRZ" crossOrigin="anonymous"></script>
    </div>
  );
}

export default App;
