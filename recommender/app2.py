from flask import Flask, render_template, request, Markup, redirect, url_for, flash, session
import random
import pandas as pd
import numpy as np
import requests
import re
import urllib.parse 
from bs4 import BeautifulSoup
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
app = Flask(__name__)
from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user
from flask_login import LoginManager
from flask_login import login_user, logout_user, login_required, current_user

app.config['SECRET_KEY'] = 'poopy'  # Replace 'your_secret_key_here' with your actual secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root@localhost/flask'
db = SQLAlchemy(app)

class SavedGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_name = db.Column(db.String(200), nullable=False)
    genre = db.Column(db.String(100), nullable=False)
    platform = db.Column(db.String(100), nullable=False)
    user_score = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    saved_games = db.relationship('SavedGame', backref='user', lazy=True)

login_manager = LoginManager(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
from forms import RegistrationForm

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        new_user = User(username=form.username.data, password=form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)
# Your LoginForm (replace this with your actual LoginForm if you have one)
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Assuming you have a User model with username and password fields
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:
            # Set the user_id in the session to indicate the user is logged in
            session['user_id'] = user.id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))  # Replace 'index' with your desired endpoint after login
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)
# Preprocessed game data
df = pd.read_csv('Video_Games.csv')

# Define the columns we want to keep for the recommendation
relevant_columns = ['Name', 'Genre', 'Platform', 'User_Score']

# Filter the DataFrame to keep only the relevant columns
df = df[relevant_columns]

# Convert the DataFrame to a list of dictionaries
games = df.to_dict(orient='records')

# Convert genres and platforms from strings to lists
for game in games:
    game['Genre'] = game['Genre'].split(',') if isinstance(game['Genre'], str) else []
    game['Platform'] = game['Platform'].split(',') if isinstance(game['Platform'], str) else []

    # Convert 'tbd' to NaN for User_Score
    if game['User_Score'] == 'tbd':
        game['User_Score'] = np.nan
    else:
        game['User_Score'] = float(game['User_Score'])

@app.route("/")
def index():
    return render_template("index.html", current_user=current_user)
def fetch_game_description(title):
    # Replace YOUR_API_KEY with your actual API key from RAWG (sign up to get the API key)
    api_key = "33b676f49ef74f21860f648158668b42"
    formatted_title = title.replace(" ", "-").replace(":", "").replace("'", "").replace(".", "").lower()

    # Remove consecutive hyphens (replace them with a single hyphen)
    formatted_title = formatted_title.replace("--", "-")    
    url = f"https://api.rawg.io/api/games/{formatted_title.lower()}?key={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        game_data = response.json()

        # Get the description from the API response
        description = game_data.get("description", "Description not available.")
        if description == "Description not available.":
            # If description is not available, create a Google search link
            google_search_link = f"https://www.google.com/search?q={urllib.parse.quote(title)}"
            return Markup(f"Description not available. <a href='{google_search_link}' target='_blank'>Search on Google</a>.")
        else:
  # Use BeautifulSoup to remove HTML elements and convert HTML entities
            soup = BeautifulSoup(description, "html.parser")
            clean_description = soup.get_text()
        # Remove HTML tags from the description using regular expression
            clean_description = re.sub('<[^<]+?>', '', description)

        # Split the description into sentences and take the first two sentences
            sentences = clean_description.split('. ')
            if len(sentences) >= 2:
                clean_description = '. '.join(sentences[:2])

            return clean_description
    except requests.exceptions.RequestException as e:
        print(f"Error fetching description for {title}: {e}")
        return "Error fetching description."
@app.route("/recommend", methods=["POST"])
@app.route("/recommend", methods=["POST"])
def recommend_games():
    genre = request.form.get("genre")
    platform = request.form.get("platform")
    user_score_threshold = float(request.form.get("user_score"))

    # Implement your recommendation logic based on user input
    recommended_games = [
        game for game in games
        if genre.lower() in [genre.lower() for genre in game["Genre"]]
        and game["Platform"] and platform.lower() in [platform.lower() for platform in game["Platform"]]
        and not np.isnan(game["User_Score"])
        and game["User_Score"] >= user_score_threshold
    ]

    # Fetch descriptions for each game using the RAWG API and save the games
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        for game in recommended_games:
            title = game['Name']
            description = fetch_game_description(title)
            saved_game = SavedGame(
                game_name=game['Name'],
                genre=', '.join(game['Genre']),
                platform=', '.join(game['Platform']),
                user_score=game['User_Score'],
                description=description,
                user_id=user_id
            )
            db.session.add(saved_game)
        db.session.commit()

    # Shuffle the recommended games list and choose 15 random games
    random.shuffle(recommended_games)
    recommended_games = recommended_games[:5]

    print(recommended_games)  # Add this line to check the content of recommended_games

    return render_template("recommendations.html", games=recommended_games)
@app.route("/save_game", methods=["POST"])
def save_game():
    if 'user_id' not in session:
        flash('You need to be logged in to save games.', 'warning')
        return redirect(url_for('login'))

    game_id = int(request.form.get('game_id'))
    user_id = session['user_id']

    # Check if the game is already saved by the user
    saved_game = SavedGame.query.filter_by(user_id=user_id, id=game_id).first()
    if saved_game:
        flash('Game already saved.', 'info')
    else:
        game = next((game for game in games if game['id'] == game_id), None)
        if game:
            new_saved_game = SavedGame(
                game_name=game['Name'],
                genre=', '.join(game['Genre']),
                platform=', '.join(game['Platform']),
                user_score=game['User_Score'],
                description=fetch_game_description(game['Name']),
                user_id=user_id
            )
            db.session.add(new_saved_game)
            db.session.commit()
            flash('Game saved successfully!', 'success')
        else:
            flash('Game not found.', 'danger')

    return redirect(url_for('index'))
@app.route('/logout')
def logout():
    # Clear the user's session data
    session.pop('user_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))
@app.route('/remove_saved_game/<int:game_id>', methods=['POST'])
def remove_saved_game(game_id):
    if 'user_id' not in session:
        flash('You need to be logged in to remove saved games.', 'warning')
        return redirect(url_for('login'))

    saved_game = SavedGame.query.get(game_id)

    if not saved_game:
        flash('Game not found.', 'danger')
        return redirect(url_for('index'))

    db.session.delete(saved_game)
    db.session.commit()
    flash('Game removed from saved games.', 'success')

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
