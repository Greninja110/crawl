# from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
# import logging
# import os
# from datetime import datetime

# # Set up logging
# logging.basicConfig(level=logging.DEBUG)

# # Create a minimal Flask app for debugging
# app = Flask(__name__)
# app.secret_key = 'debugging_secret_key'

# # Add the context processor for 'now'
# @app.context_processor
# def inject_now():
#     return {'now': datetime.now()}

# @app.route('/')
# def index():
#     return redirect(url_for('login_page'))

# @app.route('/login', methods=['GET', 'POST'])
# def login_page():
#     if request.method == 'POST':
#         flash('Login functionality is disabled in debug mode', 'warning')
#         return redirect(url_for('login_page'))
    
#     return render_template('auth/login.html')

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         flash('Registration is disabled in debug mode', 'warning')
#         return redirect(url_for('register'))
    
#     return render_template('auth/register.html')

# if __name__ == '__main__':
#     app.run(debug=True, port=5001)  # Use a different port