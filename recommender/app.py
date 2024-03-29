from flask import Flask, render_template, request, Markup, redirect, url_for, flash, session, jsonify
import random
import pandas as pd
import numpy as np
import requests
import re
import json
from datetime import timedelta 
from flask_bcrypt import Bcrypt, check_password_hash
from flask_mysqldb import MySQL
import MySQLdb.cursors

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
    current_route = request.path
    # Display welcome message if user is logged in
    if 'loggedin' in session:
        message = f'Happy gaming, {session["name"]}!'
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE user SET developed_dict = %s WHERE email = %s', ('{}', session['email']))
        mysql.connection.commit() 
        return render_template("index.html", message=message, current_route=current_route)
    else:
        return render_template("index.html", current_route=current_route)

def fetch_game_info(game_slug):
    api_key = "AIzaSyBUhOXZisi-abYLQ480sGFGwfgK7R9r8oU"
    custom_search_engine_id = "d5d4e51a640c64644"
    rawg_api_key = "33b676f49ef74f21860f648158668b42"
    game_slug_lower = game_slug.lower().replace(" ", "-").replace("'", "").replace(".", "").replace(":", "")
    
    # Check the RAWG API for game data
    rawg_url = f"https://api.rawg.io/api/games/{game_slug_lower}?key={rawg_api_key}"
    try:
        rawg_response = requests.get(rawg_url)
        rawg_response.raise_for_status()
        game_data = rawg_response.json()

        if not game_data.get("background_image"):
            # No photo found, use Google Custom Search API to look up the game_slug
            google_search_url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={custom_search_engine_id}&q={game_slug_lower}"
            
            try:
                google_response = requests.get(google_search_url)
                google_response.raise_for_status()
                google_data = google_response.json()
                
                if "items" in google_data and len(google_data["items"]) > 0:
                    # Extract the first og:image value from the first item's metatags
                    first_item = google_data["items"][0]
                    metatags = first_item.get("pagemap", {}).get("metatags", [])
                    first_metatag = metatags[0] if metatags else {}
                    photo = first_metatag.get("og:image", None)
                    print("WE GOT HIM", photo)
                else:
                    photo = None
                
                return None, [], None, [], photo, None  # Return None for other values
            except requests.exceptions.RequestException as e:
                print(f"Error fetching game info from Google: {e}")
                return None, [], None, [], None, None
            except ValueError as e:
                print(f"Error parsing game info from Google: {e}")
                return None, [], None, [], None, None
                
        else:
            # Photo found, continue with the RAWG API data
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
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching game info from RAWG: {e}")
        return None, [], None, [], None, None
    except ValueError as e:
        print(f"Error parsing game info from RAWG: {e}")
        return None, [], None, [], None, None

def fetch_and_store_recommended_games(genre, platform, user_score_threshold):
    game_info = {}
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
        deal_info = search_games([game])
        if deal_info:  # Check if there is deal information available
            game["deal_link"] = deal_info[0].get("deal_link")
            print(deal_info[0].get("cheapest"))
            game["price"]= deal_info[0].get("cheapest")
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
    #session["recommended_games"] = new_recommended_games
    #session["game_info"] = game_info
    session["favorites_list"] = favorites_list
    return new_recommended_games, game_info   
def search_games(games):
    search_results = []
    
    for game in games:
        game_title = game["Name"]  # Use the game title to search for deals
        # Construct the API URL using the entered game title
        api_url = f"https://www.cheapshark.com/api/1.0/games?title={game_title}"
        
        # Fetch the API response
        response = requests.get(api_url)
        results = response.json()
        
        if results:  # Check if results are not empty
            result = results[0]  # Get the first result
            deal_id = result.get("cheapestDealID")
            #cheapest = result.get("cheapest")
            result["deal_link"] = f"https://www.cheapshark.com/redirect?dealID={deal_id}"
            #result["cheapest"] = cheapest     
            search_results.append(result)  # Append the result to the search_results list
    print("SEARCH RESULTS")
    print(search_results)
    return search_results
@app.route('/search_game', methods=['GET'])
def search_game():
    game_title = request.args.get('game_title')
    logged_in = 'loggedin' in session
    message = f'Hello, {session["name"]}!' if logged_in and 'name' in session else None
    if game_title:
        # Construct the API URL using the entered game title
        api_url = f"https://www.cheapshark.com/api/1.0/games?title={game_title}"
        
        # Fetch the API response
        response = requests.get(api_url)
        search_results = response.json()
        
        for result in search_results:
            deal_id = result.get('cheapestDealID')
            result['deal_link'] = f"https://www.cheapshark.com/redirect?dealID={deal_id}"
        
        return render_template('search_game.html', search_results=search_results, message = message)
    
    return render_template('search_game.html')
# Route to handle the initial recommendation request
@app.route("/recommend", methods=["POST"])
def recommend_games():
    logged_in = 'loggedin' in session
    message = f'Hello, {session["name"]}!' if logged_in and 'name' in session else None    
    genre = request.form.get("genre")
    platform = request.form.get("platform")
    user_score_threshold = float(request.form.get("user_score"))
    session["game_info"] = {}
    print("THIS IS THE GAME SESSION IN RECOMMEND", session["game_info"])
    # Fetch and store the recommended games in the session
    recommended_games, game_info  = fetch_and_store_recommended_games(genre, platform, user_score_threshold)
    game_info = session.get("game_info", {})
    print("GAME INGO IN RECOMMEND", game_info)
    #print("THIS IS GAMES", games)
    return render_template("recommendations.html", games=recommended_games, game_info=game_info, message=message, logged_in=logged_in)
    #return render_template("recommendations.html", games=session["recommended_games"], game_info=game_info, message= message, logged_in=logged_in)

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
def get_game_info_by_name(game_name, diction):
    for game in diction:
        if game['name'] == game_name:
            game_info = {
                "Game Name": game['name'],
                "Rating": game['rating'],
                "Background Image URL": game['background_image'],
                "Metacritic": game['metacritic']
                # Add other relevant information as needed
            }
            return game_info
    return None
@app.route('/delete_bookmarked_games', methods=['POST'])
def delete_bookmarked_games():
    if 'loggedin' in session and session['loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE user SET bookmarked_games = %s WHERE email = %s', (json.dumps([]), session['email']))
        mysql.connection.commit()
        
        # Return an empty response (status code 200) to indicate success
        return '', 200
    else:
        # Return an empty response (status code 401) to indicate that the user is not logged in
        return '', 401

@app.route('/bookmark_game', methods=['POST'])
def bookmark_game():
    print("hi")
    
    if 'loggedin' in session and session['loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT developed_dict FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()
        
        if user and 'developed_dict' in user:
            all_games_info_json = user['developed_dict']
            print("THIS IS JSON", all_games_info_json)
            all_games_info = json.loads(all_games_info_json)
            
            # Get the name of the game from the form data
            game_name = request.form.get('game_name')
            print("This is game_name", game_name)
            
            # Find the game information in all_games_info based on game_name
            bookmarked_game_info = get_game_info_by_name(game_name, all_games_info)

            print("Bookmarked game here!!", bookmarked_game_info)
            
            if bookmarked_game_info:
                # Update the user's bookmarks list in the database
                cursor.execute('SELECT developers, bookmarked_games FROM user WHERE email = %s', (session['email'],))
                user = cursor.fetchone()
                bookmarks_list_str = user.get('developers') if user else ''
                bookmarks_list = bookmarks_list_str.split(',') if bookmarks_list_str else []
                
                if game_name not in bookmarks_list:
                    bookmarks_list.append(game_name)
                    print("BOOKMARKS_LIST BELOW")
                    print(bookmarks_list)
                    
                    # Update the user's bookmarks list in the database
                    bookmarks_list_str = ','.join(bookmarks_list)
                    cursor.execute('UPDATE user SET developers = %s WHERE email = %s', (bookmarks_list_str, session['email']))
                    
                    # Retrieve and update the bookmarked games list from the database
                    bookmarked_games_list_str = user.get('bookmarked_games') if user else ''
                    bookmarked_games_list = bookmarked_games_list_str.split('|') if bookmarked_games_list_str else []
                    
                    # Convert the bookmarked game's information dictionary to a delimited string
                    delimited_info = ','.join([str(value) for value in bookmarked_game_info.values()])
                    print("THIS IS DELIMITED INFO", delimited_info)
                    
                    # Append the new bookmarked game's delimited information to the list
                    bookmarked_games_list.append(delimited_info)
                    
                    # Convert the list back to a delimited string and update the user's bookmarked games list in the database
                    bookmarked_games_list_str = '|'.join(bookmarked_games_list)
                    print("This is bookmarked_games_list_str", bookmarked_games_list_str)
                    
                    cursor.execute('UPDATE user SET bookmarked_games = %s WHERE email = %s', (bookmarked_games_list_str, session['email']))
                    mysql.connection.commit()
                    
                    # Return an empty response (status code 200) to indicate success
# Redirect back to the developers page with a success query parameter
                    return "Game successfully bookmarked!", 200
                    #return redirect(url_for('developers', success_message="Game successfully bookmarked!"))
                else:
                    # Return an empty response (status code 200) to indicate the game is already bookmarked
                    return '', 200
            else:
                # Return an empty response (status code 400) to indicate the game name wasn't found in all_games_info
                return '', 400
        else:
            # Handle the case when developed_dict is not found in the user's record
            return '', 400
    else:
        # Return an empty response (status code 401) to indicate that the user is not logged in
        return '', 401

@app.route('/remove_bookmarked_game/<game_name>', methods=['POST'])
def remove_bookmarked_game(game_name):
    print("HEHEEHEHE")
    if 'loggedin' in session and session['loggedin']:
        print("HSAHSAH")
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT bookmarked_games FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()
        bookmarked_games_list_str = user.get('bookmarked_games') if user else ''
        print(bookmarked_games_list_str)
        print(" ")
        bookmarked_games_list = bookmarked_games_list_str.split('|') if bookmarked_games_list_str else []
        print("BOOKMARKED GAMES LIST",bookmarked_games_list)
        print(" BE FORE LOOP")
        print(" ")
        for game_info in bookmarked_games_list:
            game_edited = game_info.split(',')[0]  # Extract the game name from the comma-separated string
            if game_edited.strip() == game_name:        
        #if game_name in bookmarked_games_list:
                bookmarked_games_list.remove(game_info)  # Remove the selected game from the list
                print("BREAK IN ")
                print("REMOVED", bookmarked_games_list)
            # Update the user's bookmarked games list in the database
                updated_bookmarked_games_list_str = '|'.join(bookmarked_games_list)
                cursor.execute('UPDATE user SET bookmarked_games = %s WHERE email = %s', (updated_bookmarked_games_list_str, session['email']))
                mysql.connection.commit()
        print("AFTER LOOP")
        return redirect(url_for('show_bookmarked_games'))
    else:
        return redirect(url_for('login'))


@app.route('/bookmarked_games', methods=['GET'])
def show_bookmarked_games():
    if 'loggedin' in session and session['loggedin']:
        message = f'Welcome, {session["name"]}'
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT bookmarked_games FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()
        bookmarked_games_list_str = user.get('bookmarked_games') if user else ''
        bookmarked_games_list = bookmarked_games_list_str.split('|') if bookmarked_games_list_str else []
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE user SET developed_dict = %s WHERE email = %s', ('{}', session['email']))
        mysql.connection.commit()        
        return render_template('bookmarked_games.html', bookmarked_games_list=bookmarked_games_list, message = message)
    else:
        return redirect(url_for('login'))
@app.route('/profile')
def profile():
    if 'loggedin' in session and session['loggedin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT bookmarked_games FROM user WHERE email = %s', (session['email'],))
        user = cursor.fetchone()
        
        bookmarked_games = user.get('bookmarked_games') if user else []
        if bookmarked_games:
            print(bookmarked_games)
        
        return render_template('profile.html', bookmarked_games=bookmarked_games)
    else:
        return redirect('/login')

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
def publisher_info():
    dictionary = {'electronic-arts': 'Electronic Arts', 'square-enix': 'Square Enix', 'microsoft-studios': 'Microsoft Studios', 'ubisoft-entertainment': 'Ubisoft Entertainment', 'sega-2': 'SEGA', '2k-games': '2K Games', 'bethesda-softworks': 'Bethesda Softworks', 'feral-interactive': 'Feral Interactive', 'capcom': 'Capcom', 'valve': 'Valve', 'sony-computer-entertainment': 'Sony Computer Entertainment', 'warner-bros-interactive': 'Warner Bros. Interactive', 'thq-nordic': 'THQ Nordic', 'devolver-digital': 'Devolver Digital', 'activision-blizzard': 'Activision Blizzard', 'aspyr': 'Aspyr', 'bandai-namco-entertainment': 'Bandai Namco Entertainment', 'deep-silver': 'Deep Silver', 'nintendo': 'Nintendo', 'rockstar-games': 'Rockstar Games', 'sony-interactive-entertainment': 'Sony Interactive Entertainment', '505-games': '505 Games', 'paradox-interactive': 'Paradox Interactive', 'telltale-games': 'Telltale Games', 'thq': 'THQ', 'activison': 'Activison', 'team17-digital-ltd': 'Team17 Digital', 'focus-home-interactive': 'Focus Home Interactive', 'konami': 'Konami', '1c-softclub': '1C-SoftClub', 'bandai-namco-entertainment-us': 'BANDAI NAMCO Entertainment US', 'disney-interactive': 'Disney Interactive', 'codemasters': 'Codemasters', 'daedalic-entertainment': 'Daedalic Entertainment', 'lucasarts-entertainment': 'LucasArts Entertainment', 'plug-in-digital-2': 'Plug In Digital', 'cd-projekt-red': 'CD PROJEKT RED', 'kiss-ltd': 'Kiss', 'xbox-game-studios': 'Xbox Game Studios', '1c-company': '1C Company', 'eidos-interactive': 'Eidos Interactive', 'curve-digital': 'Curve Digital', 'double-fine-productions': 'Double Fine Productions', 'atari': 'Atari', 'tinybuild': 'tinyBuild', 'annapurna-interactive': 'Annapurna Interactive', 'buka-entertainment': 'Buka Entertainment', 'take-two-interactive': 'Take Two Interactive', 'kalypso-media': 'Kalypso Media', 'atlus': 'Atlus', 'headup-games': 'Headup Games', 'ghi-media-llc': 'GHI Media', 'fromsoftware': 'FromSoftware', 'klei-entertainment': 'Klei Entertainment', 'interplay-productions': 'Interplay Productions', 'nightdive-studios': 'Nightdive Studios', 'activision-value-publishing': 'Activision Value Publishing', 'koch-media': 'Koch Media', 'id-software': 'id Software', 'raw-fury': 'Raw Fury', 'frictional-games': 'Frictional Games', 'microids-2': 'Microids', '11-bit-studios': '11 bit studios', 'bohemia-interactive': 'Bohemia Interactive', 'blizzard-entertainment': 'Blizzard Entertainment', 'strategy-first': 'Strategy First', 'iceberg-interactive': 'Iceberg Interactive', 'forever-entertainment-s-a': 'Forever Entertainment', 'playstation-pc-llc': 'PlayStation PC', '3d-realms': '3D Realms', 'konami-digital-entertainment-us': 'Konami Digital Entertainment-US', 'tripwire-interactive': 'Tripwire Interactive', 'gt-interactive-software': 'GT Interactive Software', 'majesco-entertainment': 'Majesco Entertainment', 'rebellion': 'Rebellion', 'quantic-dream': 'Quantic Dream', 'supergiant-games': 'Supergiant Games', 'chucklefish': 'Chucklefish', 'nvidia': 'NVIDIA', 'perfect-world-entertainment': 'Perfect World Entertainment', 'back-to-basics-gaming': 'Back To Basics Gaming', 'coffee-stain-studios': 'Coffee Stain Studios', 'topware-interactive-2': 'TopWare Interactive', 'playway': 'PlayWay', 'sekai-project': 'Sekai Project', 'good-shepherd-entertainment': 'Good Shepherd Entertainment', 'playdigious': 'Playdigious', 'anuman-interactive': 'Anuman Interactive', 'square': 'Square', 'playstation-mobile-inc': 'PlayStation Mobile', 'sierra-entertainment': 'Sierra Entertainment', 'techland-publishing': 'Techland Publishing', 'gearbox-publishing': 'Gearbox Publishing', 'nicalis': 'Nicalis', 'nordic-games': 'Nordic Games', 'koei-tecmo-games': 'Koei Tecmo Games', 'stardock-entertainment': 'Stardock Entertainment', 'adult-swim-games': 'Adult Swim Games', 'funbox-media': 'Funbox Media', 'sierra-on-line': 'Sierra On-Line', 'versus-evil': 'Versus Evil', 'fellow-traveller': 'Fellow Traveller', 'merge-games': 'Merge Games', 'dotemu': 'DotEmu', 'virgin-interactive': 'Virgin Interactive', 'humble-bundle': 'Humble Bundle', 'grabthegames': 'GrabTheGames', 'meridian4': 'Meridian4', 'infogrames': 'Infogrames', 'jackbox-games': 'Jackbox Games', 'snk': 'SNK', 'vivendi-universal-games': 'Vivendi Universal Games', 'larian-studios': 'Larian Studios', 'akella': 'Akella', 'bandai-namco-entertainment-europe': 'BANDAI NAMCO Entertainment Europe', 'xseed-games': 'XSEED Games', 'agm-playism': 'AGM PLAYISM', 'wwwhandy-gamescom': 'www.handy-games.com', 'new-reality-games': 'New Reality Games', 'degica': 'Degica', 'alawar-entertainment': 'Alawar Entertainment', 'bloober-team': 'Bloober Team', 'gt-interactive': 'GT Interactive', 'ci-games': 'CI Games', 'bungie': 'Bungie', 'frozenbyte': 'Frozenbyte', 'digerati': 'Digerati', 'gsc-game-world': 'GSC Game World', 'handygames': 'HandyGames', 'introversion-software': 'Introversion Software', 'sometimes-you': 'Sometimes You', 'artifex-mundi': 'Artifex Mundi', 'aksys-games': 'Aksys Games', 'virgin-interactive-entertainment': 'Virgin Interactive Entertainment', 'hi-rez-studios': 'Hi-Rez Studios', 'fatshark': 'Fatshark', 'viva-meda': 'Viva Meda', 'humble-games': 'Humble Games', 'drinkbox-studios': 'DrinkBox Studios', 'surprise-attack': 'Surprise Attack', 'bigben-interactive': 'Bigben Interactive', 'asmodee-digital': 'Asmodee Digital', 'blitworks': 'BlitWorks', 'cyberfront': 'CyberFront', 'oddworld-inhabitants': 'Oddworld Inhabitants', 'frogwares': 'Frogwares', 'hypetrain-digital': 'HypeTrain Digital', 'xd-network': 'X.D. Network', 'daybreak-game-company': 'Daybreak Game Company', 'digerati-distribution': 'Digerati Distribution', 'private-division': 'Private Division', 'alawar-premium': 'Alawar Premium', 'gameloft': 'Gameloft', 'frontier-developments': 'Frontier Developments', 'amanita-design': 'Amanita Design', 'retroism': 'Retroism', 'namco': 'Namco', 'zachtronics': 'Zachtronics', 'd3publisher': 'D3 Publisher', '8-4': '8-4', 'funcom': 'Funcom', 'nis-america': 'NIS America', 'marvelous-usa': 'Marvelous USA', 'microsoft-game-studios': 'Microsoft Game Studios', 'digital-extremes': 'Digital Extremes', 'spike-chunsoft-co-ltd': 'Spike Chunsoft Co', 'skybound-games': 'Skybound Games', 'trion-worlds': 'Trion Worlds', 'atlus-usa-2': 'Atlus USA', 'fishlabs': 'FISHLABS', 'empire-interactive': 'Empire Interactive', 'apogee-software': 'Apogee Software', 'winged-cloud': 'Winged Cloud', 'wargaming': 'Wargaming', 'running-with-scissors': 'Running With Scissors', 'missing-link-games': 'Missing Link Games', 'spike-chunsoft': 'Spike Chunsoft', 'nacon': 'Nacon', 'gaijin-entertainment': 'Gaijin Entertainment', 'acclaim-entertainment': 'Acclaim Entertainment', 'remedy-entertainment': 'Remedy Entertainment', 'wb-games': 'WB Games', 'assemble-entertainment': 'Assemble Entertainment', 'psyonix': 'Psyonix', 'io-interactive': 'Io-Interactive', 'bossa-studios': 'Bossa Studios', 'ak-tronic-software-services': 'ak tronic Software & Services', 'arc-system-works': 'Arc System Works', 'freebird-games': 'Freebird Games', 'revolution-software': 'Revolution Software', 'inxile-entertainment': 'inXile Entertainment', 'taleworlds-entertainment': 'TaleWorlds Entertainment', 'ensenasoft': 'EnsenaSoft', 'croteam': 'Croteam', 'playdead': 'Playdead', '4eversgames': '4EversGames', 'ea-sports': 'EA SPORTS', 'landfall': 'Landfall', 'modus-games': 'Modus Games', 'nordic-games-publishing': 'Nordic Games Publishing'}
    return dictionary
def developer_info():
    dev_dict = {'ubisoft': 'Ubisoft', 'feral-interactive': 'Feral Interactive', 'valve-software': 'Valve Software', 'ubisoft-montreal': 'Ubisoft Montreal', 'electronic-arts': 'Electronic Arts', 'sony-interactive-entertainment': 'Sony Interactive Entertainment', 'square-enix': 'Square Enix', 'capcom': 'Capcom', 'aspyr-media': 'Aspyr Media', 'bethesda-softworks': 'Bethesda Softworks', 'sega': 'SEGA', 'warner-bros-interactive': 'Warner Bros. Interactive', 'bandai-namco-entertainment-america-inc': 'BANDAI NAMCO Entertainment America', 'devolver-digital': 'Devolver Digital', 'capcom-usa-inc': 'Capcom U.S.A', 'telltale-games': 'Telltale Games', 'thq-nordic': 'THQ Nordic', '2k': '2K', 'id-software': 'id Software', 'nvidia-lightspeed-studios': 'NVIDIA Lightspeed Studios', 'gearbox-software': 'Gearbox Software', 'bioware': 'BioWare', 'nintendo': 'Nintendo', 'konami-digital-entertainment': 'Konami Digital Entertainment', 'raven-software': 'Raven Software', 'naughty-dog': 'Naughty Dog', 'rockstar-north': 'Rockstar North', 'cd-projekt-red': 'CD PROJEKT RED', 'bethesda-game-studios': 'Bethesda Game Studios', 'digital-extremes': 'Digital Extremes', 'codemasters': 'Codemasters', 'ea-dice': 'Electronic Arts DICE', 'rockstar-games': 'Rockstar Games', 'team17-digital': 'Team17 Digital', 'crystal-dynamics': 'Crystal Dynamics', '505-games': '505 Games', 'deep-silver': 'Deep Silver', 'daedalic-entertainment': 'Daedalic Entertainment', 'io-interactive-2': 'IO Interactive', 'fromsoftware': 'FromSoftware', 'double-fine-productions': 'Double Fine Productions', 'arkane-studios': 'Arkane Studios', 'activision': 'Activision', 'travellers-tales': "Traveller's Tales", 'relic-entertainment': 'Relic Entertainment', 'firaxis': 'Firaxis', 'lucasarts-entertainment': 'LucasArts Entertainment', 'volition': 'Volition', 'plug-in-digital': 'Plug In Digital', '2k-australia': '2K Australia', 'obsidian-entertainment': 'Obsidian Entertainment', 'turtle-rock-studios': 'Turtle Rock Studios', 'treyarch': 'Treyarch', 'bandai-namco-entertainment': 'Bandai Namco Entertainment', '2k-marin': '2K Marin', 'ubisoft-toronto': 'Ubisoft Toronto', 'panic-button': 'Panic Button', 'lucasfilm': 'Lucasfilm', 'creative-assembly': 'Creative Assembly', 'croteam': 'Croteam', 'remedy-entertainment': 'Remedy Entertainment', 'techland': 'Techland', 'ubisoft-montpellier': 'Ubisoft Montpellier', 'avalanche-studios': 'Avalanche Studios', 'monolith-productions': 'Monolith Productions', 'epic-games': 'Epic Games', 'dontnod-entertainment': 'DONTNOD Entertainment', 'virtuos': 'Virtuos', 'insomniac-games': 'Insomniac Games', 'infinity-ward': 'Infinity Ward', 'eidos-montreal': 'Eidos Montreal', 'nerve-software': 'Nerve Software', 'curve-digital': 'Curve Digital', 'tinybuild': 'tinyBuild', 'klei-entertainment': 'Klei Entertainment', 'ubisoft-shanghai-2': 'Ubisoft Shanghai', 'netherrealm-studios': 'NetherRealm Studios', 'beenox': 'Beenox', 'vicarious-visions': 'Vicarious Visions', 'thq': 'THQ', 'crytek': 'Crytek', '2k-china': '2K China', 'ea-canada': 'Electronic Arts Canada', 'platinumgames': 'Platinum Games', 'respawn-entertainment': 'Respawn Entertainment', 'bungie-inc': 'Bungie', '4a-games': '4A Games', 'qloc': 'QLOC', 'high-voltage-software': 'High Voltage Software', 'rocksteady-studios': 'Rocksteady Studios', 'frozenbyte': 'Frozenbyte', 'rebellion': 'Rebellion', 'kojima-productions': 'Kojima Productions', '11-bit-studios': '11 Bit Studios', 'quantic-dream': 'Quantic Dream', 'irrational-games': 'Irrational Games', 'microids': 'Microids', 'paradox-development-studio': 'Paradox Development Studio', '3d-realms': '3D Realms', 'frictional-games': 'Frictional Games', 'sledgehammer-games': 'Sledgehammer Games', 'supergiant-games': 'Supergiant Games', 'haemimont-games': 'Haemimont Games', 'ubisoft-quebec': 'Ubisoft Quebec', 'double-eleven': 'Double Eleven', 'annapurna-interactive': 'Annapurna Interactive', 'dotemu': 'DotEmu', 'bohemia-interactive': 'Bohemia Interactive', 'splash-damage': 'Splash Damage', 'tango-gameworks': 'Tango Gameworks', 'ryu-ga-gotoku-studio': 'Ryu ga Gotoku Studio', 'sumo-digital': 'Sumo Digital', 'atlus': 'Atlus', 'criterion-games': 'Criterion Games', 'saber-interactive': 'Saber Interactive', 'ubisoft-bucharest': 'Ubisoft Bucharest', '343-industries': '343 Industries', 'koei-tecmo': 'Koei Tecmo', 'handy-games': 'Handy Games', 'sonic-team': 'Sonic Team', 'rare': 'Rare', 'playdigious': 'Playdigious', '8-4': '8-4', 'guerrilla-games': 'Guerrilla Games', 'triumph-studios': 'Triumph Studios', 'paradox-interactive': 'Paradox Interactive', 'high-moon-studios': 'High Moon Studios', 'piranha-bytes': 'Piranha Bytes', 'focus-home-interactive': 'Focus Home Interactive', 'arc-system-works': 'Arc System Works', 'square': 'Square', 'anuman-interactive': 'Anuman Interactive', 'hi-rez-studios': 'Hi-Rez Studios', 'popcap-games': 'PopCap Games', 'machine-games': 'Machine Games', 'gsc-game-world': 'GSC Game World', 'sucker-punch-productions': 'Sucker Punch Productions', 'snk': 'SNK', 'stardock-entertainment': 'Stardock Entertainment', 'abstraction-games': 'Abstraction Games', 'jackbox-games': 'Jackbox Games', 'tripwire-interactive': 'Tripwire Interactive', 'kalypso-media': 'Kalypso Media', 'vigil-games': 'Vigil Games', 'larian-studios': 'Larian Studios', 'cyanide-studio': 'Cyanide Studio', 'playground-games': 'Playground Games', 'flying-wild-hog': 'Flying Wild Hog', 'cd-projekt-sa': 'CD PROJEKT', 'gameloft': 'Gameloft', 'frontier-developments': 'Frontier Developments', 'alawar-entertainment': 'Alawar Entertainment', 'war-drum-studios': 'War Drum Studios', 'frogwares': 'Frogwares', 'visceral-games': 'Visceral Games', 'bloober-team-sa': 'Bloober Team', 'hangar-13': 'Hangar 13', 'nicalis': 'Nicalis', 'microprose-software': 'MicroProse Software', 'amplitude-studios': 'Amplitude Studios', 'visual-concepts': 'Visual Concepts', 'armature-studio': 'Armature Studio', 'fatshark': 'Fatshark', '2k-czech': '2K Czech', 'escalation-studios': 'Escalation Studios', 'edge-of-reality': 'Edge of Reality', 'coffee-stain-studios': 'Coffee Stain Studios', 'headup-games': 'Headup Games', 'dennaton-games': 'Dennaton Games', 'introversion-software': 'Introversion Software', 'engine-software': 'Engine Software', 'n-space': 'n-Space', 'starbreeze-studios': 'Starbreeze Studios', 'grasshopper-manufacture': 'Grasshopper Manufacture', 'rockstar-san-diego': 'Rockstar San Diego', 'playdead': 'Playdead', 'hidden-path-entertainment': 'Hidden Path Entertainment', 'maxis': 'Maxis', 'ubisoft-kiev': 'Ubisoft Kiev', 'supermassive-games': 'Supermassive Games', 'arrowhead-game-studios': 'Arrowhead Game Studios', 'sony-computer-entertainment-america': 'Sony Computer Entertainment America', 'spike-chunsoft': 'Spike Chunsoft', 'santa-monica-studio': 'Santa Monica Studio', 'interplay-entertainment': 'Interplay Entertainment', 'sce-santa-monica-studio': 'SCE Santa Monica Studio', 'red-storm': 'Red Storm', 'team-ninja': 'Team NINJA', 'certain-affinity': 'Certain Affinity', 'codeglue': 'Codeglue', 'wayforward-technologies': 'WayForward Technologies', 'oddworld-inhabitants': 'Oddworld Inhabitants', 'lionhead-studios': 'Lionhead Studios', 'ninja-theory': 'Ninja Theory', 'ubisoft-annecy': 'Ubisoft Annecy', 'game-freak': 'Game Freak', 'ubisoft-paris': 'Ubisoft Paris', 'asobo-studio': 'Asobo Studio', 'people-can-fly': 'People Can Fly', 'gunfire-games': 'Gunfire Games'}
    return dev_dict
@app.route('/clear_games_info')
def clear_all_games_info():
    if 'all_games_info' in session:
        session.pop('all_games_info', None)
        print("AFTER POP", session['all_games_info'])
    return redirect(url_for('index'))  # Redirect to another route, e.g., index

#THIS IS WHERE THE COOKIE PROBLEM HAPPENS
@app.route('/developers')
def developers():
    developer_dictionary = developer_info()
    logged_in = 'loggedin' in session
    message = f'Hello, {session["name"]}!' if logged_in and 'name' in session else None
    
    selected_developer = request.args.get('selected_developer')
    #success_message = request.args.get('success_message')

    if selected_developer:
        api_key = '33b676f49ef74f21860f648158668b42'
        url = f'https://api.rawg.io/api/games?key={api_key}&developers={selected_developer}&ordering=-rating&page_size=10'
        modified_value = selected_developer.replace('-', ' ').title()

        response = requests.get(url)
        games_data = response.json()
        if 'results' in games_data:
            all_games_info = []  # Create an empty list to store game information

            for game_data in games_data['results']:
                game_info = {
                    'name': game_data.get('name', None),
                    'rating': game_data.get('rating', None),
                    'background_image': game_data.get('background_image', None),
                    'platforms': game_data.get('platforms', []),
                    'metacritic': game_data.get('metacritic', None),
                    'genres': game_data.get('genres', []),
                    'stores': game_data.get('stores', []),
                    'developers': game_data.get('developers', []),
                }
                all_games_info.append(game_info)  # Append each game_info dictionary to the list
            #session['all_games_info'] = all_games_info  # Store all_games_info in the session
            #COOKIE TOO BIGGGG
            all_games_info_json = json.dumps(all_games_info)

            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            #cursor.execute('SELECT develolped_dict FROM user WHERE email = %s', (session['email'],))
            #user = cursor.fetchone()
            cursor.execute('UPDATE user SET developed_dict = %s WHERE email = %s', (all_games_info_json, session['email']))
            mysql.connection.commit()

            print("ALL GAMES INFO:", all_games_info)  # Print the list of all games' information
            print(type(all_games_info))
            return render_template('games.html', games=all_games_info, selected=modified_value, message= message,  logged_in=logged_in)

    return render_template('developers.html', developer_dictionary=developer_dictionary, message= message, logged_in=logged_in)

@app.route('/get_games', methods=['POST'])
def get_games():
    if 'loggedin' in session and session['loggedin']:
        message = f'Hello, {session["name"]}!'
    logged_in = 'loggedin' in session
    developer = request.form['developer']
    api_key = '33b676f49ef74f21860f648158668b42'
    url = f'https://api.rawg.io/api/games?key={api_key}&developers={developer}&ordering=-rating&page_size=10'
    
    response = requests.get(url)
    games_data = response.json()

    return render_template('games.html', games=games_data['results'], logged_in=logged_in, message = message)
import ast
@app.route('/favorites', endpoint='favorites', methods=['GET', 'POST'])
def show_favorites():
    current_route = request.path
    if 'loggedin' in session and session['loggedin']:
        message = f'Hello, {session["name"]}!'
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE user SET developed_dict = %s WHERE email = %s', ('{}', session['email']))
        mysql.connection.commit()        
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

            return render_template('favorites.html', favorites=filtered_favorite_games, game_info=session.get('game_info', {}), current_route = current_route, message=message)
        else:
            # If there is no search query, show all favorite games
            return render_template('favorites.html', favorites=favorite_games_dict, game_info=session.get('game_info', {}), current_route = current_route, message=message)
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
@app.route('/redirect_to_home')
def redirect_to_home():
    # Call the clear_game_info function
    clear_game_info()

    # Redirect to the home page
    return redirect(url_for('index'))

#new
@app.route('/developer_search', methods=['GET'])
def developer_search():
    return render_template('developer_search.html')
@app.route('/fetch_developer_slugs', methods=['GET'])
def fetch_developer_slugs():
    # Make a request to the RAWG API to fetch a list of developer slugs
    rawg_api_key = "33b676f49ef74f21860f648158668b42"
    url = f"https://api.rawg.io/api/developers?key={rawg_api_key}&page_size=100"

    response = requests.get(url)
    data = response.json()

    developer_slugs = [developer.get('slug', 'Unknown') for developer in data.get('results', [])]

    return jsonify({'developer_slugs': developer_slugs})
#end of new

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

        # Update the 'favorites' column in the database with the modified favorites_list
        cursor.execute('UPDATE user SET favorite_games = %s WHERE email = %s', (session['game_info'], session['email']))
        
        # Update the 'game_info' column in the database with the JSON string
        cursor.execute('UPDATE user SET game_info = %s WHERE email = %s', (new_game_info_json, session['email']))
        
        mysql.connection.commit()

        print("After removing non-favorite games from game_info:", session['game_info'])
    else:
        print("'game_info' not found in the session.")
    return 'game_info session cleared!'



    
if __name__ == "__main__":
    app.run(debug=True)
