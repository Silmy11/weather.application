from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
from pymysql.cursors import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
from urllib.parse import quote  # Added for safe web search encoding

app = Flask(__name__)
app.secret_key = 'super_secret_weather_key'

# ==========================================
# MYSQL CONFIGURATION VARIABLES
# ==========================================
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mysql@11") 
DB_NAME = "weather_db"

# SECURE: Keep your API key here on the backend server.
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

def get_db_connection():
    """Establishes and returns a connection to the active MySQL database."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True, 
        cursorclass=DictCursor 
    )

# ==========================================
# BACKEND API ROUTES (Secure Proxy & History)
# ==========================================
@app.route('/api/weather/<city>')
def get_weather_proxy(city):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    
    # Encode city names (e.g., converts 'New York' to 'New%20York') so the external API understands it
    safe_city_name = quote(city)
    
    current_url = f"https://api.openweathermap.org/data/2.5/weather?q={safe_city_name}&appid={WEATHER_API_KEY}&units=metric"
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={safe_city_name}&appid={WEATHER_API_KEY}&units=metric"
    
    current_res = requests.get(current_url)
    if current_res.status_code != 200:
        return jsonify({'error': 'City not found'}), 404
        
    forecast_res = requests.get(forecast_url)
    
    # Log search straight into MySQL history tables
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('INSERT INTO search_history (user_id, city_name) VALUES (%s, %s)', (user_id, city.title()))
    finally:
        conn.close()
        
    return jsonify({
        'current': current_res.json(),
        'forecast': forecast_res.json()
    })

@app.route('/api/favorites', methods=['POST'])
def add_favorite():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    data = request.get_json()
    city = data.get('city', '').strip().title()
    
    if not city:
        return jsonify({'error': 'Invalid city name'}), 400
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute('INSERT INTO favorites (user_id, city_name) VALUES (%s, %s)', (user_id, city))
                return jsonify({'success': True, 'message': 'Added to favorites'})
            except pymysql.IntegrityError:
                return jsonify({'success': True, 'message': 'Already in favorites'})
    finally:
        conn.close()

# ==========================================
# USER PROFILE ROUTE
# ==========================================
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get Saved Favorite Cities
            cursor.execute('SELECT city_name FROM favorites WHERE user_id = %s ORDER BY city_name ASC', (user_id,))
            favs = [row['city_name'] for row in cursor.fetchall()]
            
            # Get Last 10 Recent Searches
            cursor.execute('SELECT city_name, searched_at FROM search_history WHERE user_id = %s ORDER BY searched_at DESC LIMIT 10', (user_id,))
            history = [{'city': row['city_name'], 'time': row['searched_at'].strftime('%Y-%m-%d %H:%M:%S')} for row in cursor.fetchall()]
    finally:
        conn.close()
        
    return render_template('profile.html', username=session['username'], favorites=favs, history=history)

# ==========================================
# STANDARD PAGES & AUTH
# ==========================================
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Please fill out all fields.', 'error')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password, method='scrypt')
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, hashed_password))
            flash('Registration successful! Log in now.', 'success')
            return redirect(url_for('login'))
        except pymysql.IntegrityError:
            flash('Username already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
        finally:
            conn.close()
            
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
