# This application provides a web interface to query and display information
# about New Zealand's wildlife species and their conservation status

from flask import Flask, g, render_template, request, redirect, flash, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)
app.secret_key = '************'  

# Define database file path
DATABASE = 'NZ_Wildlife.db'

def get_db():
    """Get database connection, create only once per request"""
    if not hasattr(g, '_database'):
        g._database = sqlite3.connect(DATABASE)
        g._database.row_factory = sqlite3.Row  
    return g._database

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection at end of request"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/")
def home():
    """Home page with species overview"""
    db = get_db()
    cursor = db.cursor()
    
    selected_field = request.args.get('field', default=None)
    
    try:
        # Get all necessary data in a single transaction
        cursor.execute("SELECT * FROM Species LIMIT 100")  # Limit for performance
        species_results = cursor.fetchall()

        cursor.execute("SELECT * FROM Origin_Status")
        origin_status_results = cursor.fetchall()

        cursor.execute("SELECT * FROM Species_Type")
        species_type_results = cursor.fetchall()

        cursor.execute("SELECT * FROM Status")
        status_results = cursor.fetchall()

        # Create status lookup dictionary
        status_dict = {row[0]: row[1] for row in status_results}
        
    except sqlite3.Error as e:
        print(f"Database error in home route: {e}")
        # Return empty data if database error occurs
        species_results = []
        origin_status_results = []
        species_type_results = []
        status_results = []
        status_dict = {}
    finally:
        cursor.close()
    
    # Define field indices for template
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
        species=species_results,
        origin_status=origin_status_results,
        species_type=species_type_results,
        status=status_results,
        status_dict=status_dict,
        selected_field=selected_field,
        field_indices=field_indices
    )

@app.route("/species")
def species():
    """Species search and listing page"""
    db = get_db()
    cursor = db.cursor()
    search_query = request.args.get('name', default='', type=str).strip()
    
    try:
        if search_query:
            # Simplified search query
            search_param = f'%{search_query.lower()}%'
            cursor.execute("""
                SELECT *, 'Search Result' as matched_field
                FROM Species s
                WHERE LOWER(s.species_name) LIKE ?
                   OR LOWER(s.scientific_name) LIKE ?
                   OR LOWER(s.species_type) LIKE ?
                   OR LOWER(s.family) LIKE ?
                ORDER BY s.species_name
                LIMIT 50
            """, [search_param, search_param, search_param, search_param])
        else:
            # Display limited species for performance
            cursor.execute("SELECT *, NULL as matched_field FROM Species ORDER BY species_name LIMIT 50")
        
        results = cursor.fetchall()
        
    except sqlite3.Error as e:
        print(f"Database error in species route: {e}")
        results = []
    finally:
        cursor.close()
    
    return render_template("species.html", species=results, search_query=search_query)

@app.route('/add', methods=["GET", "POST"])
def add():
    """Add new species entry"""
    if request.method == "POST":
        try:
            new_name = request.form.get("item_name", "").strip()
            new_description = request.form.get("item_description", "").strip()

            if new_name and new_description:  
                db = get_db()
                cursor = db.cursor()
                cursor.execute("INSERT INTO Species (species_name, scientific_name) VALUES (?, ?)", 
                             (new_name, new_description))
                db.commit()
                cursor.close()
                flash('Species added successfully!', 'success')
            else:
                flash('Both name and description are required', 'error')
                
        except sqlite3.Error as e:
            print(f"Database error in add route: {e}")
            flash('Error adding species', 'error')

    return redirect('/')

@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration"""
    if request.method == "POST":
        email = request.form.get('email', '').strip()
        password = request.form.get('psw', '')
        password_repeat = request.form.get('psw-repeat', '')
        
        # Validation
        if not all([email, password, password_repeat]):
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
            db = get_db()
            cursor = db.cursor()
            
            # Check if user already exists
            cursor.execute("SELECT usernames FROM Users WHERE usernames = ?", (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash('Email already registered', 'error')
                return render_template("register.html")
            
            # Hash password and insert user
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO Users (usernames, passwords) VALUES (?, ?)", 
                         (email, hashed_password))
            db.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect('/login')
            
        except sqlite3.Error as e:
            print(f"Database error in register route: {e}")
            flash('Registration failed. Please try again.', 'error')
        finally:
            if 'cursor' in locals():
                cursor.close()
        
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """User login"""
    if request.method == "POST":
        email = request.form.get('email', '').strip()
        password = request.form.get('psw', '')
        
        if not all([email, password]):
            flash('Email and password are required', 'error')
            return render_template("login.html")
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            cursor.execute("SELECT usernames, passwords FROM Users WHERE usernames = ?", (email,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[1], password):
                session['user_email'] = email
                flash('Login successful!', 'success')
                return redirect('/')
            else:
                flash('Invalid email or password', 'error')
                
        except sqlite3.Error as e:
            print(f"Database error in login route: {e}")
            flash('Login failed. Please try again.', 'error')
        finally:
            if 'cursor' in locals():
                cursor.close()
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    """User logout"""
    session.pop('user_email', None)
    flash('You have been logged out', 'info')
    return redirect('/login')

@app.route("/favourites")
def favourites():
    """Favourites page"""
    return render_template("favourites.html")

@app.route("/api/search-suggestions")
def search_suggestions():
    """API endpoint for search suggestions"""
    try:
        query = request.args.get('q', '').lower().strip()
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        
        db = get_db()
        cursor = db.cursor()
        
        if show_all or len(query) == 0:
            cursor.execute("""
                SELECT species_name, scientific_name, species_type, family
                FROM Species 
                WHERE species_name IS NOT NULL
                ORDER BY species_name
                LIMIT 15
            """)
        else:
            search_param = f'%{query}%'
            cursor.execute("""
                SELECT species_name, scientific_name, species_type, family
                FROM Species 
                WHERE (LOWER(species_name) LIKE ? OR LOWER(scientific_name) LIKE ?)
                  AND species_name IS NOT NULL
                ORDER BY 
                    CASE WHEN LOWER(species_name) LIKE ? THEN 1 ELSE 2 END,
                    species_name
                LIMIT 10
            """, [search_param, search_param, f'{query}%'])
        
        results = cursor.fetchall()
        
        suggestions = []
        for row in results:
            if row[0]:  # species_name exists
                suggestions.append({
                    'text': row[0],
                    'type': f'{row[2]} - {row[3]}' if row[2] and row[3] else (row[2] or 'Unknown')
                })
        
        return jsonify({'suggestions': suggestions})
        
    except sqlite3.Error as e:
        print(f"Database error in search suggestions: {e}")
        return jsonify({'suggestions': []})
    except Exception as e:
        print(f"Error in search suggestions: {e}")
        return jsonify({'suggestions': []})
    finally:
        if 'cursor' in locals():
            cursor.close()

@app.route("/api/species")
def api_species():
    """API endpoint for species data"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT * FROM Species ORDER BY species_name LIMIT 100")
        species_results = cursor.fetchall()
        
        species_list = []
        for species in species_results:
            species_dict = {
                'id': species[0] if len(species) > 0 else None,
                'species_name': species[1] if len(species) > 1 else None,
                'scientific_name': species[2] if len(species) > 2 else None,
                'species_type': species[3] if len(species) > 3 else None,
                'origin_status': species[4] if len(species) > 4 else None,
                'predator': species[5] if len(species) > 5 else None,
                'prey': species[6] if len(species) > 6 else None,
                'status': species[7] if len(species) > 7 else None,
                'family': species[8] if len(species) > 8 else None,
                'numbers': species[9] if len(species) > 9 else None,
                'image_url': species[10] if len(species) > 10 and species[10] else None
            }
            species_list.append(species_dict)
        
        return jsonify(species_list)
        
    except sqlite3.Error as e:
        print(f"Database error in api_species: {e}")
        return jsonify([])
    except Exception as e:
        print(f"Error in api_species: {e}")
        return jsonify([])
    finally:
        if 'cursor' in locals():
            cursor.close()

@app.route("/map")
def map_page():
    """Interactive map page"""
    return render_template("map.html")

@app.route("/about")
def about():
    """About page"""
    return render_template("about.html")

def init_db():
    """Initialize database tables"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usernames TEXT UNIQUE NOT NULL,
                passwords TEXT NOT NULL
            )
        ''')
        db.commit()
        cursor.close()
        print("Database initialized successfully")
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, threaded=True)