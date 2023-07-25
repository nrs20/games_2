from flask import Flask, render_template, request
import requests

app = Flask(__name__)

RAWG_API_KEY = "33b676f49ef74f21860f648158668b42"  # Replace with your actual RAWG API key


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/recommend", methods=["POST"])
def recommend_games():
    genre = request.form.get("genre")
    platform = request.form.get("platform")
    rating = float(request.form.get("rating"))

    headers = {"User-Agent": "Game Recommender App"}
    url = f"https://api.rawg.io/api/games?key={RAWG_API_KEY}&genres={genre}&platforms={platform}&metacritic={rating}&page_size=10"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        recommended_games = data["results"]
        return render_template("recommendations.html", games=recommended_games)
    except requests.exceptions.RequestException as e:
        return f"Error fetching data: {e}"


if __name__ == "__main__":
    app.run(debug=True)
