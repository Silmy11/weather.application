import os
import sqlite3
from datetime import datetime
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'dev_secret_key_1234'

DATABASE = 'weather_dashboard.db'

# ========================================================
# 1. READ API KEY DIRECTLY AS A STRING (NO ENV NEEDED)
# ========================================================
API_KEY = "YOUR_API_KEY"
# =======================================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Connect and check if the 'users' table actually exists inside the database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query SQLite system tables to see if 'users' exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        print("[DATABASE INFO] Tables missing. Creating fresh SQLite database layers...")
        with app.open_resource('schema.sql', mode='r') as f:
            cursor.executescript(f.read())
        conn.commit()
        print("[DATABASE INFO] Database system initiated successfully with schema.sql.")
    else:
        print("[DATABASE INFO] Database tables verified. Skipping initialization.")
        
    conn.close()

@app.context_processor
def inject_user():
    return dict(is_logged_in=('user_id' in session))

# --- AUTHENTICATION ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
            
        conn = get_db_connection()
        try:
            hashed_password = generate_password_hash(password)
            conn.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                (username, email, hashed_password)
            )
            conn.commit()
            print(f"[AUTH SUCCESS] Registered new user: {username}")
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            print(f"[AUTH ERROR] Registration failed. Username/Email already exists.")
            flash('Username or Email already exists.', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            print(f"[AUTH SUCCESS] Logged in user session: {user['username']}")
            flash(f"Welcome back, {user['username']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            print("[AUTH ERROR] Invalid username or password authentication attempt.")
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    print(f"[AUTH INFO] Ending user session: {session.get('username')}")
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# --- DASHBOARD PLATFORM CONTROLLERS ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    
    # Fetch Favorites
    fav_rows = conn.execute('SELECT city FROM favorites WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()
    favorites = [row['city'] for row in fav_rows]
    
    # Fetch History
    history_rows = conn.execute(
        'SELECT city, searched_at FROM search_history WHERE user_id = ? ORDER BY id DESC LIMIT 5', 
        (user_id,)
    ).fetchall()
    
    history = [{'city': row['city'], 'time': row['searched_at']} for row in history_rows]
    conn.close()
    
    return render_template('index.html', username=session['username'], favorites=favorites, history=history)


# --- WEATHER DATA FETCH API LAYER ---

@app.route('/api/weather', methods=['GET'])
def get_weather_data():
    if 'user_id' not in session:
        print("[API WARNING] Unauthorized API endpoint query block triggered.")
        return jsonify({'error': 'Unauthorized'}), 401
        
    city = request.args.get('city')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    user_id = session['user_id']
    
    print(f"[API INFO] Received tracking query request. Parameters -> City: {city}, Lat: {lat}, Lon: {lon}")
    
    if not API_KEY or API_KEY == 'PASTE_YOUR_OPENWEATHER_API_KEY_HERE':
        print("[CRITICAL ERROR] OpenWeather API Key is completely missing or left as placeholder text!")
        return jsonify({'error': 'OpenWeatherMap API Key configuration is missing on the server.'}), 500

    try:
        if lat and lon:
            print(f"[API INFO] Resolving coordinate telemetry parameters via reverse geocode...")
            geo_url = f"https://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={API_KEY}"
            geo_res = requests.get(geo_url).json()
            if not geo_res:
                print("[API ERROR] Could not resolve coordinates to any valid city name targets.")
                return jsonify({'error': 'Could not resolve location coordinates.'}), 404
            city = geo_res[0]['name']
            print(f"[API INFO] Resolved coordinates to target city name: {city}")
        elif city:
            city = city.strip()
        else:
            return jsonify({'error': 'City name or coordinates required.'}), 400

        # 1. Fetch Current Metrics
        print(f"[API INFO] Querying OpenWeatherMap Current Conditions API for: {city}")
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={API_KEY}"
        w_response = requests.get(weather_url)
        
        if w_response.status_code != 200:
            print(f"[API ERROR] OpenWeatherMap server rejected query with HTTP Code: {w_response.status_code}. Response: {w_response.text}")
            return jsonify({'error': 'City not found or upstream API error.'}), w_response.status_code
            
        w_data = w_response.json()
        target_lat = w_data['coord']['lat']
        target_lon = w_data['coord']['lon']
        resolved_city_name = w_data['name']

        # 2. Fetch Air Quality Index (AQI)
        print(f"[API INFO] Querying Air Pollution Levels API for coordinates: {target_lat}, {target_lon}")
        aqi_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={target_lat}&lon={target_lon}&appid={API_KEY}"
        aqi_data = requests.get(aqi_url).json()
        aqi_val = aqi_data['list'][0]['main']['aqi']

        # 3. Fetch 5-Day Forecast Matrix
        print(f"[API INFO] Querying 5-Day Forecast Matrix API for coordinates: {target_lat}, {target_lon}")
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={target_lat}&lon={target_lon}&units=metric&appid={API_KEY}"
        f_data = requests.get(forecast_url).json()

        # Update tracking database logs histories
        conn = get_db_connection()
        conn.execute('INSERT INTO search_history (user_id, city) VALUES (?, ?)', (user_id, resolved_city_name))
        conn.commit()
        conn.close()
        print(f"[DATABASE INFO] Saved '{resolved_city_name}' cleanly into user search history logs.")

        # Organize payload tracking structure metrics fields
        payload = {
            'current': {
                'city': resolved_city_name,
                'temp': round(w_data['main']['temp']),
                'feels_like': round(w_data['main']['feels_like']),
                'humidity': w_data['main']['humidity'],
                'wind_speed': w_data['wind']['speed'],
                'pressure': w_data['main']['pressure'],
                'visibility': round(w_data.get('visibility', 0) / 1000, 1),
                'description': w_data['weather'][0]['description'].title(),
                'icon': w_data['weather'][0]['icon'],
                'sunrise': datetime.fromtimestamp(w_data['sys']['sunrise']).strftime('%I:%M %p'),
                'sunset': datetime.fromtimestamp(w_data['sys']['sunset']).strftime('%I:%M %p'),
                'aqi': aqi_val
            },
            'forecast': []
        }

        # Subsample down interval structures
        seen_days = set()
        for item in f_data['list']:
            date_txt = item['dt_txt'].split(' ')[0]
            date_obj = datetime.strptime(date_txt, '%Y-%m-%d')
            day_name = date_obj.strftime('%A')
            
            if day_name not in seen_days and len(payload['forecast']) < 5:
                seen_days.add(day_name)
                payload['forecast'].append({
                    'day': day_name,
                    'date': date_obj.strftime('%b %d'),
                    'temp': round(item['main']['temp']),
                    'humidity': item['main']['humidity'],
                    'description': item['weather'][0]['description'].title(),
                    'icon': item['weather'][0]['icon']
                })

        print(f"[API SUCCESS] Successfully aggregated weather data for '{resolved_city_name}'. Dispatching JSON payload...")
        return jsonify(payload)

    except Exception as e:
        print(f"[CRITICAL APPLICATION EXCEPTION] Runtime traceback trace failure error context: {str(e)}")
        return jsonify({'error': 'An internal data aggregation error occurred.'}), 500


# --- FAVORITES ACTIONS INTERFACE ---

@app.route('/api/favorites', methods=['GET', 'POST', 'DELETE'])
def manage_favorites():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    conn = get_db_connection()
    
    if request.method == 'GET':
        rows = conn.execute('SELECT city FROM favorites WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()
        conn.close()
        return jsonify([row['city'] for row in rows])
        
    data = request.get_json() or {}
    city = data.get('city', '').strip()
    
    if not city:
        conn.close()
        return jsonify({'error': 'City context parameter missing'}), 400
        
    if request.method == 'POST':
        try:
            conn.execute('INSERT INTO favorites (user_id, city) VALUES (?, ?)', (user_id, city))
            conn.commit()
            print(f"[DATABASE INFO] User added favorite target location parameter: {city}")
            return jsonify({'success': f'{city} added to favorites.'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'info': 'City already added'}), 200
        finally:
            conn.close()
            
    elif request.method == 'DELETE':
        conn.execute('DELETE FROM favorites WHERE user_id = ? AND LOWER(city) = LOWER(?)', (user_id, city))
        conn.commit()
        conn.close()
        print(f"[DATABASE INFO] User deleted favorite target location parameter: {city}")
        return jsonify({'success': f'{city} removed from favorites.'})


if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
