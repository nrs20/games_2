from flask import Flask, render_template, request, Markup, redirect, url_for, flash, session, jsonify
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
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL
import MySQLdb.cursors
app = Flask(__name__)

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'user-sysstem'  # Replace with your database name
app.secret_key = 'xyzsdfg'

mysql = MySQL(app)

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

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM user WHERE email = %s AND password = %s', (email, password,))
        user = cursor.fetchone()
        if user:
            session['loggedin'] = True
            session['name'] = user['name']
            session['email'] = user['email']
            message = 'Logged in successfully!'
            return redirect(url_for('index'))  # Redirect to the recommendation page
        else:
            message = 'Please enter correct email / password!'
    return render_template('login.html', message=message)

# Logout route
@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('login'))  # Redirect to the login page

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM user WHERE email = %s', (email,))
        account = cursor.fetchone()
        if account:
            message = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = 'Invalid email address!'
        elif not username or not password or not email:
            message = 'Please fill out the form!'
        else:
            cursor.execute('INSERT INTO user (username, email, password) VALUES (%s, %s, %s)', (username, email, password,))
            mysql.connection.commit()
            message = 'You have successfully registered!'
    elif request.method == 'POST':
        message = 'Please fill out the form!'
    return render_template('register.html', message=message)

@app.route("/")
def index():
    # Display welcome message if user is logged in
    if 'loggedin' in session:
        return render_template("index.html", username=session['name'])
    else:
        return render_template("index.html")
"""def fetch_game_description(title):
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
        return "Error fetching description."""

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

    # Fetch the user's favorites list from the database
    favorites_list = []
    if 'loggedin' in session and session['loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT favorites FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()
        if user:
            favorites_list_str = user.get('favorites')
            favorites_list = favorites_list_str.split(',') if favorites_list_str else []

    # Create a list to store the recommended games that are not in favorites
    new_recommended_games = []

    for game in recommended_games:
        if game['Name'] not in favorites_list:
            new_recommended_games.append(game)

    # Fetch descriptions for each game using the RAWG API and store them in the 'Description' field
    #for game in new_recommended_games:
      #  title = game['Name']
       # game['Description'] = fetch_game_description(title)

    # Shuffle the new recommended games list and choose 5 random games
    random.shuffle(new_recommended_games)
    new_recommended_games = new_recommended_games[:5]

    return render_template("recommendations.html", games=new_recommended_games)

# Rest of the code ...
@app.route('/save_game', methods=['POST'])
def save_game():
    if 'loggedin' in session and session['loggedin']:
        # Get the name of the game from the form data
        game_name = request.form.get('game_name')

        # Get the user's favorites list from the database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT favorites FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()

        # Extract the existing favorites list or create an empty list if it's None
        favorites_list_str = user.get('favorites') if user else ''
        favorites_list = favorites_list_str.split(',') if favorites_list_str else []

        # Add the game name to the favorites list if it's not already in there
        if game_name not in favorites_list:
            favorites_list.append(game_name)

            # Update the user's favorites list in the database
            favorites_list_str = ','.join(favorites_list)
            cursor.execute('UPDATE user SET favorites = %s WHERE email = %s', (favorites_list_str, session['email'],))
            mysql.connection.commit()

            # Return an empty response (status code 200) to indicate success
            return '', 200
        else:
            # Return an empty response (status code 200) to indicate the game already exists in favorites
            return '', 200
    else:
        # Return an empty response (status code 401) to indicate that the user is not logged in
        return '', 401
@app.route('/favorites', endpoint='favorites')
def show_favorites():
    if 'loggedin' in session and session['loggedin']:
        # Get the user's favorites list from the database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT favorites FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()

        # Extract the existing favorites list or create an empty list if it's None
        favorites_list_str = user.get('favorites') if user else ''
        favorites_list = favorites_list_str.split(',') if favorites_list_str else []

        # Get the complete game data for each game in the favorites list
        favorite_games = [game for game in games if game['Name'] in favorites_list]

        # Attach the Reddit URL to the favorite games
        for game in favorite_games:
            reddit_url = game.get('reddit_url')
            game['Reddit_URL'] = reddit_url if reddit_url else 'No Reddit URL available.'

        return render_template('favorites.html', favorites=favorite_games)
    else:
        return redirect(url_for('login'))

@app.route('/remove_from_favorites', methods=['POST'])
def remove_from_favorites():
    if 'loggedin' in session and session['loggedin']:
        # Get the name of the game to be removed from the form data
        game_name = request.form.get('game_name')

        # Get the user's favorites list from the database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT favorites FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()

        # Extract the existing favorites list or create an empty list if it's None
        favorites_list_str = user.get('favorites') if user else ''
        favorites_list = favorites_list_str.split(',') if favorites_list_str else []

        # Remove the game name from the favorites list if it's in there
        if game_name in favorites_list:
            favorites_list.remove(game_name)

            # Update the user's favorites list in the database
            favorites_list_str = ','.join(favorites_list)
            cursor.execute('UPDATE user SET favorites = %s WHERE email = %s', (favorites_list_str, session['email'],))
            mysql.connection.commit()

            # Redirect back to the favorites page after removing the game
            return redirect(url_for('favorites'))
        else:
            # If the game is not in the favorites list, do nothing
            flash('Game not found in favorites.')
            return redirect(url_for('favorites'))
    else:
        return redirect(url_for('login'))  # Redirect to the login page if not logged in
if __name__ == "__main__":
    app.run(debug=True)
