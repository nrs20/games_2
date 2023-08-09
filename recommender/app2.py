from flask import Flask, render_template, request, Markup, redirect, url_for, flash, session, jsonify
import random
import pandas as pd
import numpy as np
import requests
import re
from flask import copy_current_request_context
import json
import urllib.parse
from datetime import timedelta 
from bs4 import BeautifulSoup
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from flask_bcrypt import Bcrypt, check_password_hash
from flask_mysqldb import MySQL
import MySQLdb.cursors
from flask_paginate import Pagination, get_page_args

app = Flask(__name__)
bcrypt = Bcrypt(app)
# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=5)

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
        cursor.execute('SELECT * FROM user WHERE email = %s', (email,))
        user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):  # Verify hashed password
            session['loggedin'] = True
            session['name'] = user['name']
            session['email'] = user['email']
            session['message'] = message  # Add the message to the session
            game_info_json = user.get('game_info', None)
            if game_info_json:
                session['game_info'] = json.loads(game_info_json)
            else:
                session['game_info'] = {}  # Initialize an empty dictionary if no game_info found
            return redirect(url_for('index'))  # Redirect to the recommendation page
        else:
            message = 'Please enter correct email / password!'
    return render_template('login.html', message=message)
@app.route('/clear_session')
def clear_session():
    session.clear()
    return 'Session cleared!'

# Logout route
@app.route('/logout')
def logout():
    if 'game_info' in session:
        game_info_json = json.dumps(session['game_info'])
        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE user SET game_info = %s WHERE email = %s', (game_info_json, session['email'],))
        mysql.connection.commit()
    if 'message' in session:
        session.pop('message')
    session.clear()  # Clear all session data
    return redirect(url_for('login'))  # Redirect to the login page

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST' and 'name' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['name']
        plain_password = request.form['password']
        email = request.form['email']
        
        # Optional: Get other form fields if needed
        # field4 = request.form['field4']
        # field5 = request.form['field5']
        # field6 = request.form['field6']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM user WHERE email = %s', (email,))
        account = cursor.fetchone()

        if account:
            message = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = 'Invalid email address!'
        elif not username or not plain_password or not email:
            message = 'Please fill out the form!'
        else:
            # Hash the password before storing it
            hashed_password = bcrypt.generate_password_hash(plain_password).decode('utf-8')
            
            # Optional: Provide NULL for fields not in the form
            # You can set the value of fields not in the form as None
            # field4 = None
            # field5 = None
            # field6 = None
            
            # Insert the data into the database
            cursor.execute('INSERT INTO user (name, email, password) VALUES (%s, %s, %s)',
                           (username, email, hashed_password))
            mysql.connection.commit()
            message = 'You have successfully registered!'
    elif request.method == 'POST':
        message = 'Please fill out the form!'
    return render_template('register.html', message=message)

@app.route("/")
def index():
    # Display welcome message if user is logged in
    if 'loggedin' in session:
        message = f'Welcome, {session["name"]}!'
        return render_template("index.html", message=message)
    else:
        return render_template("index.html")

def fetch_game_info(game_slug):
    api_key = "33b676f49ef74f21860f648158668b42"
    game_slug = game_slug.lower().replace(" ", "-").replace("'", "").replace(".", "").replace(":", "")
    url = f"https://api.rawg.io/api/games/{game_slug}?key={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        game_data = response.json()

        if game_data:
            reddit_url = game_data.get("reddit_url", None)
            developers = game_data.get("developers", [])
            meta = game_data.get("metacritic_url", None)
            photo = game_data.get("background_image", None)
            website = game_data.get("website", None)

            # Get the stores information
            stores = []
            for store_data in game_data.get("stores", []):
                store_name = store_data["store"]["name"]
                store_domain = store_data["store"]["domain"]

                stores.append({"name": store_name, "domain": store_domain})

            developer_names = [developer["name"] for developer in developers]
            return reddit_url, developer_names, meta, stores, photo, website  # Include stores information
        else:
            return None, [], None, []  # Return None for all values when no game data is found

    except requests.exceptions.RequestException as e:
        print(f"Error fetching game info: {e}")
        return None, [], None, []
    except ValueError as e:
        print(f"Error parsing game info: {e}")
        return None, [], None, []



def fetch_and_store_recommended_games(genre, platform, user_score_threshold):
    # Implement your recommendation logic based on user input
    recommended_games = [
        game for game in games
        if genre.lower() in [genre.lower() for genre in game["Genre"]]
        and game["Platform"] and platform.lower() in [platform.lower() for platform in game["Platform"]]
        and not np.isnan(game["User_Score"])
        and game["User_Score"] >= user_score_threshold
    ]

    # Fetch the user's favorites list from the database and create a list of recommended games that are not in favorites
    favorites_list = session.get("favorites_list", [])
    new_recommended_games = [game for game in recommended_games if game['Name'] not in favorites_list]

    # Fetch the existing game_info from the session, or initialize an empty dictionary
    game_info = session.get("game_info", {})

    # Initialize an empty dictionary for the current genre if it doesn't already exist
    if genre not in game_info:
        game_info[genre] = {}

    # Update the game_info with the fetched data for the current genre
    for game in new_recommended_games:
        title = game['Name']
        game_slug = title.lower().replace(" ", "-")  # Format the title to create the API request URL
        #game_info[genre][title] = fetch_game_info(game_slug)
        reddit_url, developer_names, meta, stores, photo, website = fetch_game_info(game_slug)
        game_info[genre][title] = {
            "reddit_url": reddit_url,
            "developers": developer_names,
            "metacritic":meta,
            "stores": stores,
            "photo": photo,
            "website": website,
            "platform": game['Platform']

        }
        # Update the game dictionary with the fetched data
        if game_info[genre].get(title):
            # Check if game_info[genre][title] is a dictionary before accessing 'Reddit_URL'
            if isinstance(game_info[genre][title], dict):
                game['reddit_url'] = game_info[genre][title].get('reddit_url', None)
                game['metacritic'] = game_info[genre][title].get('metacritic_url', None)
                game['developers'] = developer_names
                game['stores'] =  stores
                game['photo'] =  photo
                game['website'] =  website

            else:
                game['reddit_url'] = None
                game['metacritic'] = None
                game['developers'] = None
                game['stores'] = None
                game['photo'] = None
                game['website'] = None


    # Shuffle the new recommended games
    random.shuffle(new_recommended_games)
   # print("game_info:", game_info)
    #print("--------------------------------")
    #print(game_info['Action']['Bloodborne'][0])
    print("-----------------------")

    # Store the shuffled recommended games and the updated game_info for the current genre in the session
    session["recommended_games"] = new_recommended_games
    session["game_info"] = game_info
    session["favorites_list"] = favorites_list


# Route to handle the initial recommendation request
@app.route("/recommend", methods=["POST"])
def recommend_games():
    genre = request.form.get("genre")
    platform = request.form.get("platform")
    user_score_threshold = float(request.form.get("user_score"))

    # Fetch and store the recommended games in the session
    fetch_and_store_recommended_games(genre, platform, user_score_threshold)
    game_info = session.get("game_info", {})
    print("GAME INGO IN RECOMMEND", game_info)
    #print("THIS IS GAMES", games)
    return render_template("recommendations.html", games=session["recommended_games"], game_info=game_info)

# Route to handle the regenerate button click
@app.route("/regenerate", methods=["POST"])
def regenerate_games():
    # Check if recommended games are already stored in the session
    if "recommended_games" in session:
        # Shuffle the existing recommended games
        random.shuffle(session["recommended_games"])

    # Shuffle the game_info dictionary for the current genre (assuming you have the 'genre' available in the session)
    genre = session.get("current_genre")
    if genre and genre in session.get("game_info", {}):
        game_info = session["game_info"]
        game_info[genre] = dict(random.sample(game_info[genre].items(), len(game_info[genre])))

    return jsonify({"status": "success"}), 200

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

import ast
@app.route('/favorites', endpoint='favorites', methods=['GET', 'POST'])
def show_favorites():
    if 'loggedin' in session and session['loggedin']:
        # Check if game_info session is present
        if 'game_info' not in session:
            # Fetch the game information from the 'favorite_games' column in the database
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT favorite_games FROM user WHERE email = %s', (session['email'],))
            user = cursor.fetchone()

            # Get the JSON string from the database and convert it to a Python dictionary
            favorite_games_str = user.get('favorite_games') if user and user.get('favorite_games') else '{}'
            favorite_games_dict = ast.literal_eval(favorite_games_str)

            # Create an empty dictionary to store game_info
            game_info = {}
            # Loop through the favorite_games_dict to collect the required information
            for game_name, game_data in favorite_games_dict.items():
                genre = game_data['Genre'][0]  # Assuming you have one genre for each game in the 'Genre' list

                # Get the reddit_url, developers, and metacritic from the game_data
                reddit_url = game_data.get('reddit_url')
                developers = game_data.get('developers')
                meta = game_data.get('metacritic')
                stores = game_data.get('stores')
                photo = game_data.get('photo')
                website = game_data.get('website')

                # Create a dictionary with the game_name as the key and the required information as the value
                game_info_data = {
                    'reddit_url': reddit_url if reddit_url else 'No Reddit URL available.',
                    'developers': developers if developers else 'No developer available',
                    'metacritic': meta if meta else 'No Metacritic URL available.',
                    'stores': stores if stores else 'No Store URL available.',
                    'photo': photo if photo else 'No Photo URL available.',
                    'website': website if website else 'No website URL available.'

                }

                # Add the game_info_data to the corresponding genre in the game_info dictionary
                game_info.setdefault(genre, {})
                game_info[genre][game_name] = game_info_data

            # Save the game_info dictionary in the session
            session['game_info'] = game_info

        # Get the user's favorites list from the database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT favorites FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()

        # Extract the existing favorites list or create an empty list if it's None
        favorites_list_str = user.get('favorites') if user else ''
        favorites_list = favorites_list_str.split(',') if favorites_list_str else []

        # Get the complete game data for each game in the favorites list
        favorite_games = [game for game in games if game['Name'] in favorites_list]

        # Fetch the game info from the session
        game_info = session.get('game_info', {})

        # Convert the favorite_games list into a dictionary with game names as keys and game data as values
        favorite_games_dict = {}
        for game in favorite_games:
            game_name = game['Name']
            if game_name not in favorite_games_dict:
                favorite_games_dict[game_name] = game

        # Attach the Reddit URL, developers, and metacritic to the favorite games from the game_info
        for game_name, game_data in favorite_games_dict.items():
            genre = game_data['Genre'][0]  # Assuming you have one genre for each game in the 'Genre' list

            # Get the game_info for the corresponding genre from the session
            game_info_genre = game_info.get(genre, {})
            # Get the game_info for the specific game title from the genre's game_info
            game_info_data = game_info_genre.get(game_name, {})

            # Get the reddit_url, developers, and metacritic from the game_info
            reddit_url = game_info_data.get('reddit_url')
            developers = game_info_data.get('developers')
            meta = game_info_data.get('metacritic')
            stores = game_info_data.get('stores')
            photo = game_info_data.get('photo')
            website = game_info_data.get('website')

            # Update the game_data dictionary with the retrieved data
            game_data['reddit_url'] = reddit_url if reddit_url else 'No Reddit URL available.'
            game_data['developers'] = developers if developers else 'No developer available'
            game_data['metacritic'] = meta if meta else 'No Metacritic URL available.'
            game_data['stores'] = stores if stores else 'No Store URL available.'
            game_data['photo'] = photo if photo else 'No Photo URL available.'
            game_data['website'] = website if website else 'No website URL available.'

        # Implement search functionality
        search_query = request.args.get('search')
        if search_query:
            filtered_favorite_games = {}
            for game_name, game_data in favorite_games_dict.items():
                if search_query.lower() in game_name.lower():
                    filtered_favorite_games[game_name] = game_data

            # Remove the non-matching games from the game_info as well
            for genre in game_info:
                game_info_genre = game_info[genre]
                for game_name in list(game_info_genre.keys()):
                    if game_name not in filtered_favorite_games:
                        del game_info_genre[game_name]

            return render_template('favorites.html', favorites=filtered_favorite_games, game_info=session.get('game_info', {}))
        else:
            # If there is no search query, show all favorite games
            return render_template('favorites.html', favorites=favorite_games_dict, game_info=session.get('game_info', {}))
        # Convert the favorite_games_dict to a JSON string
        favorite_games_json = json.dumps(favorite_games_dict)

        # Update the 'favorite_games' column in the database with the JSON string
        cursor.execute('UPDATE user SET favorite_games = %s WHERE email = %s', (favorite_games_json, session['email'],))
        mysql.connection.commit()

        return render_template('favorites.html', favorites=favorite_games_dict, game_info=session.get('game_info', {}))
    else:
        return redirect(url_for('login'))

""""""
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

@app.route('/clear_game_info')
def clear_game_info():
    if 'game_info' in session:
        game_info = session['game_info']
        
        # Get the user's favorites list from the database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT favorites FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()
        favorites_list_str = user.get('favorites') if user else ''
        favorites_list = favorites_list_str.split(',') if favorites_list_str else []

        # Remove game information for games not in favorites
        new_game_info = {genre: {title: info for title, info in genre_data.items() if title in favorites_list} 
                         for genre, genre_data in game_info.items()}
        
        # Update the game_info session
        session['game_info'] = new_game_info

        # Convert the new_game_info dictionary to JSON format
        new_game_info_json = json.dumps(new_game_info)

        # Update the 'game_info' column in the database with the JSON string
        cursor.execute('UPDATE user SET game_info = %s WHERE email = %s', (new_game_info_json, session['email'],))
        mysql.connection.commit()

        print("After removing non-favorite games from game_info:", session['game_info'])
    else:
        print("'game_info' not found in the session.")
    return 'game_info session cleared!'


    
if __name__ == "__main__":
    app.run(debug=True)
