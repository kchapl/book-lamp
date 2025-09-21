from flask import Flask, render_template
from flask_basicauth import BasicAuth

app = Flask(__name__)

app.config['BASIC_AUTH_USERNAME'] = 'admin'
app.config['BASIC_AUTH_PASSWORD'] = 'n1vl3k'

basic_auth = BasicAuth(app)

@app.route('/')
@basic_auth.required
def home():
    return '<h1>Hello World!</h1><p>My simple Python web app is running!</p>'

@app.route('/about')
@basic_auth.required
def about():
    return '<h1>About</h1><p>This is a simple Flask web application.</p>'

if __name__ == '__main__':
    app.run(debug=True)
