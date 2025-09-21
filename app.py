from flask import Flask
from flask_basicauth import BasicAuth
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
    password = db.Column(db.String(80), nullable=False)

class MyAuth(BasicAuth):
    def check_credentials(self, username, password):
        user = User.query.filter_by(user_name=username).first()
        if user and user.password == password:
            return True
        return False

basic_auth = MyAuth(app)

@app.route('/')
@basic_auth.required
def home():
    return '<h1>Hello World!</h1><p>My simple Python web app is running!</p>'

@app.route('/about')
@basic_auth.required
def about():
    return '<h1>About</h1><p>This is a simple Flask web application.</p>'

@app.cli.command("init-db")
def init_db():
    """Initialize the database and create/update a default user."""
    db.create_all()
    username = os.environ.get('DEFAULT_USERNAME', 'admin')
    password = os.environ.get('DEFAULT_PASSWORD', 'admin')
    user = User.query.filter_by(user_name=username).first()
    if user:
        user.password = password
        print(f"Default user '{username}' password updated.")
    else:
        user = User(user_name=username, password=password)
        db.session.add(user)
        print(f"Default user '{username}' created.")
    db.session.commit()
    print("Database initialized.")

if __name__ == '__main__':
    app.run(debug=True)
