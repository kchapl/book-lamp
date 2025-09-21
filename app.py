from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Hello World!</h1><p>My simple Python web app is running!</p>'

@app.route('/about')
def about():
    return '<h1>About</h1><p>This is a simple Flask web application.</p>'

if __name__ == '__main__':
    app.run(debug=True)
    