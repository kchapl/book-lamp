from flask import Flask, session, redirect, url_for, render_template
from authlib.integrations.flask_client import OAuth
from flask_sqlalchemy import SQLAlchemy
import click
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=True)
    google_id = db.Column(db.String(120), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    name = db.Column(db.String(120), nullable=True)

class AllowedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)



from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('unauthorized'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        return f'<h1>Hello {user.name}!</h1><p>My simple Python web app is running!</p><a href="/logout">Logout</a>'
    return '<h1>Hello World!</h1><p>You are not logged in.</p><a href="/login">Login with Google</a>'

@app.route('/about')
@login_required
def about():
    return '<h1>About</h1><p>This is a simple Flask web application.</p>'

@app.route('/unauthorized')
def unauthorized():
    return render_template('unauthorized.html'), 401

# Secret key for session management
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Google OAuth configuration
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')
app.config['GOOGLE_DISCOVERY_URL'] = "https://accounts.google.com/.well-known/openid-configuration"

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@app.route('/login')
def login():
    if 'CODESPACE_NAME' in os.environ and 'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN' in os.environ:
        codespace_name = os.environ['CODESPACE_NAME']
        domain = os.environ['GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN']
        redirect_uri = f'https://{codespace_name}-5000.{domain}/authorize'
    else:
        redirect_uri = url_for('authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.userinfo(token=token)
    
    # Check if user is in the allow list
    if not AllowedUser.query.filter_by(email=user_info['email']).first():
        return redirect(url_for('unauthorized'))

    # Check if user exists, if not create a new one
    user = User.query.filter_by(google_id=user_info['sub']).first()
    if not user:
        user = User(
            google_id=user_info['sub'],
            email=user_info['email'],
            name=user_info['name'],
            user_name=user_info['email']
        )
        db.session.add(user)
        db.session.commit()

    # Store user in session
    session['user_id'] = user.user_id
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

@app.cli.command("init-db")
def init_db_command():
    """Drop all tables and re-initialize the database."""
    db.drop_all()
    db.create_all()
    click.echo("Database re-initialized (all data was deleted).")

@app.cli.command("add-user")
@click.argument("email")
def add_user(email):
    """Add a user to the allow list."""
    if AllowedUser.query.filter_by(email=email).first():
        print(f"User {email} already in allow list.")
        return

    new_user = AllowedUser(email=email)
    db.session.add(new_user)
    db.session.commit()
    print(f"User {email} added to allow list.")

if __name__ == '__main__':
    app.run(debug=True)
