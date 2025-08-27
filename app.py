# This application provides a web interface to query and display information
# about New Zealand's wildlife species and their conservation status

# Import necessary libraries
from flask import Flask, g, render_template, request, redirect, flash, session, jsonify
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import re

db = SQLAlchemy()

app = Flask(__name__)
app.secret_key = '************'  

# Define database file path
DATABASE = 'NZ_Wildlife.db'

def get_db():
    if not hasattr(g, '_database'):
        g._database = sqlite3.connect(DATABASE)
        g._database.row_factory = sqlite3.Row  
    return g._database


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/")
def home():
    db = get_db()
    cursor = db.cursor()
    
    # Get the selected field from the query parameter
    selected_field = request.args.get('field', default=None)
    
    # Get all data from the Species table
    cursor.execute("SELECT * FROM Species")
    species_results = cursor.fetchall()

    # Get all data from the Origin_Status table
    cursor.execute("SELECT * FROM Origin_Status")
    origin_status_results = cursor.fetchall()

    # Get all data from the Species_Type table
    cursor.execute("SELECT * FROM Species_Type")
    species_type_results = cursor.fetchall()

    # Get all data from the Status table
    cursor.execute("SELECT * FROM Status")
    status_results = cursor.fetchall()

    # Debug: Print what we have
    print("First species record:", species_results[0] if species_results else "No species")
    print("Status table:", status_results)
    print("Species status values:", [row[7] for row in species_results[:3]] if species_results else "No species")

    # Create a status lookup dictionary
    status_dict = {row[0]: row[1] for row in status_results}
    print("Status dictionary:", status_dict)
    
    cursor.close()
    
    # Define mapping of field names to column indices for template use
    field_indices = {
        'species_name': 1,
        'scientific_name': 2,
        'species_type': 3,
        'origin_status': 4,
        'predator': 5,
        'prey': 6,
        'status': 7,
        'family': 8,
        'numbers': 9
    }
    
    return render_template(
        "index.html", 
        species=species_results,  # Use original species data
        origin_status=origin_status_results,
        species_type=species_type_results,
        status=status_results,
        status_dict=status_dict,
        selected_field=selected_field,
        field_indices=field_indices
    )


@app.route("/species")
def species():
    cursor = get_db().cursor()
    search_query = request.args.get('name', default='', type=str).lower()
    
    if search_query:
        # Search across all relevant fields
        cursor.execute("""
            SELECT DISTINCT s.*, 
                   CASE 
                       WHEN LOWER(s.species_name) LIKE ? THEN 'Species Name'
                       WHEN LOWER(s.scientific_name) LIKE ? THEN 'Scientific Name'
                       WHEN LOWER(s.species_type) LIKE ? THEN 'Species Type'
                       WHEN LOWER(s.origin_status) LIKE ? THEN 'Origin Status'
                       WHEN LOWER(s.predator) LIKE ? THEN 'Predator'
                       WHEN LOWER(s.prey) LIKE ? THEN 'Prey'
                       WHEN LOWER(s.status) LIKE ? THEN 'Status'
                       WHEN LOWER(s.family) LIKE ? THEN 'Family'
                       WHEN LOWER(s.numbers) LIKE ? THEN 'Numbers'
                   END as matched_field
            FROM species s
            WHERE LOWER(s.species_name) LIKE ?
               OR LOWER(s.scientific_name) LIKE ?
               OR LOWER(s.species_type) LIKE ?
               OR LOWER(s.origin_status) LIKE ?
               OR LOWER(s.predator) LIKE ?
               OR LOWER(s.prey) LIKE ?
               OR LOWER(s.status) LIKE ?
               OR LOWER(s.family) LIKE ?
               OR LOWER(s.numbers) LIKE ?
        """, ['%' + search_query + '%'] * 18)  # 9 for CASE + 9 for WHERE
    else:
        # If no search query, display all species
        cursor.execute("SELECT *, NULL as matched_field FROM species")
    
    results = cursor.fetchall()
    cursor.close()
    return render_template("species.html", species=results, search_query=search_query)


@app.route('/add', methods=["GET", "POST"])
def add():
    if request.method == "POST":
        try:
            new_name = request.form.get("item_name")
            new_description = request.form.get("item_description")

            if new_name and new_description:  
                cursor = get_db().cursor()
                cursor.execute("INSERT INTO species (name, description) VALUES (?, ?)", (new_name, new_description))
                get_db().commit()
                cursor.close()
        except sqlite3.Error as e:
            print("Database error:", e)

    return redirect('/')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('psw')
        password_repeat = request.form.get('psw-repeat')
        
        # Validation
        if not email or not password or not password_repeat:
            flash('All fields are required', 'error')
            return render_template("register.html")
        
        # Email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            flash('Please enter a valid email address', 'error')
            return render_template("register.html")
        
        # Password validation
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template("register.html")
        
        if password != password_repeat:
            flash('Passwords do not match', 'error')
            return render_template("register.html")
        
        try:
            cursor = get_db().cursor()
            
            # Check if user already exists (try different table name cases)
            try:
                cursor.execute("SELECT usernames FROM Users WHERE usernames = ?", (email,))
                existing_user = cursor.fetchone()
            except sqlite3.OperationalError:
                # Try lowercase table name if uppercase doesn't exist
                cursor.execute("SELECT usernames FROM users WHERE usernames = ?", (email,))
                existing_user = cursor.fetchone()
            
            if existing_user:
                flash('Email already registered', 'error')
                cursor.close()
                return render_template("register.html")
            
            # Hash the password
            hashed_password = generate_password_hash(password)
            
            # Insert new user (try different table name cases)
            try:
                cursor.execute("INSERT INTO Users (usernames, passwords) VALUES (?, ?)", 
                             (email, hashed_password))
            except sqlite3.OperationalError:
                # Try lowercase table name if uppercase doesn't exist
                cursor.execute("INSERT INTO users (usernames, passwords) VALUES (?, ?)", 
                             (email, hashed_password))
            
            get_db().commit()
            cursor.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect('/login')
            
        except sqlite3.Error as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template("register.html")
        
    return render_template("register.html")
  

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('psw')
        
        # Validation
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template("login.html")
        
        try:
            cursor = get_db().cursor()
            
            # Try to find user (try different table name cases)
            try:
                cursor.execute("SELECT usernames, passwords FROM Users WHERE usernames = ?", (email,))
                user = cursor.fetchone()
            except sqlite3.OperationalError:
                # Try lowercase table name if uppercase doesn't exist
                cursor.execute("SELECT usernames, passwords FROM users WHERE usernames = ?", (email,))
                user = cursor.fetchone()
            
            cursor.close()
            
            if user and check_password_hash(user[1], password):
                # Login successful
                session['user_email'] = email
                flash('Login successful!', 'success')
                return redirect('/')
            else:
                flash('Invalid email or password', 'error')
                return render_template("login.html")
                
        except sqlite3.Error as e:
            flash(f'Login failed: {str(e)}', 'error')
            return render_template("login.html")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop('user_email', None)
    flash('You have been logged out', 'info')
    return redirect('/login')


@app.route("/favourites")
def favourites():
    """Route for the favourites page"""
    return render_template("favourites.html")
    
    
# Add this updated route to your app.py file (replace the existing search_suggestions route)

@app.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get('q', '').lower().strip()
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    
    cursor = get_db().cursor()
    
    if show_all or len(query) == 0:
        # Show all species when requested or when no query
        cursor.execute("""
            SELECT DISTINCT species_name, scientific_name, species_type, family
            FROM species 
            ORDER BY species_name
            LIMIT 20
        """)
        
        results = cursor.fetchall()
        cursor.close()
        
        suggestions = []
        for row in results:
            suggestions.append({
                'text': row[0],
                'type': f'{row[2]} - {row[3]}' if row[3] else row[2]
            })
            # Also add scientific name as a separate option
            if row[1] and row[1] != row[0]:
                suggestions.append({
                    'text': row[1],
                    'type': f'Scientific Name - {row[2]}'
                })
        
        return {'suggestions': suggestions[:15]}  # Limit to 15 for better UX
    
    elif len(query) >= 1:  # Changed from 2 to 1 for more responsive searching
        # Search for matching species names and scientific names
        cursor.execute("""
            SELECT DISTINCT species_name, scientific_name, species_type, family
            FROM species 
            WHERE LOWER(species_name) LIKE ? 
               OR LOWER(scientific_name) LIKE ?
               OR LOWER(species_type) LIKE ?
               OR LOWER(family) LIKE ?
            ORDER BY 
                CASE 
                    WHEN LOWER(species_name) LIKE ? THEN 1
                    WHEN LOWER(scientific_name) LIKE ? THEN 2
                    ELSE 3 
                END,
                species_name
            LIMIT 10
        """, ['%' + query + '%'] * 4 + [query + '%'] * 2)
        
        results = cursor.fetchall()
        cursor.close()
        
        suggestions = []
        for row in results:
            # Add species name if it matches
            if query in row[0].lower():
                suggestions.append({
                    'text': row[0],
                    'type': f'{row[2]} - {row[3]}' if row[3] else row[2]
                })
            # Add scientific name if it matches and is different
            if query in row[1].lower() and row[1] != row[0]:
                suggestions.append({
                    'text': row[1],
                    'type': f'Scientific Name - {row[2]}'
                })
            # Add by type/family if they match
            if query in row[2].lower():
                suggestions.append({
                    'text': row[0],
                    'type': f'Type: {row[2]}'
                })
        
        return {'suggestions': suggestions[:10]}
    
    return {'suggestions': []}

@app.route("/api/species")
def api_species():
    """API endpoint to get all species data as JSON for favourites functionality"""
    cursor = get_db().cursor()
    
    # Get all species data
    cursor.execute("SELECT * FROM Species")
    species_results = cursor.fetchall()
    
    # Convert to list of dictionaries for JSON response
    species_list = []
    for species in species_results:
        species_dict = {
            'id': species[0],
            'species_name': species[1],
            'scientific_name': species[2],
            'species_type': species[3],
            'origin_status': species[4],
            'predator': species[5],
            'prey': species[6],
            'status': species[7],
            'family': species[8],
            'numbers': species[9],
            'image_url': species[10] if len(species) > 10 and species[10] else None
        }
        species_list.append(species_dict)
    
    cursor.close()
    
    # Return JSON response
    from flask import jsonify
    return jsonify(species_list)

@app.route("/map")
def map_page():
    """Route for the interactive map page"""
    return render_template("map.html")

@app.route("/about")
def about():
    """Route for the about page"""
    return render_template("about.html")

def init_db():
    cursor = get_db().cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usernames TEXT UNIQUE NOT NULL,
            passwords TEXT NOT NULL
        )
    ''')
    get_db().commit()
    cursor.close()

# Add this line before if __name__ == "__main__":
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)

if __name__ == "__main__":
    app.run(debug=False)
    