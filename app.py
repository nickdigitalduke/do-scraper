from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import os
import threading
import json
from script import run_scraper as run_trustoo_scraper
from werkspot_scraper import run_werkspot_scraper

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Log in om toegang te krijgen tot de scraper.'

# Simpele user class
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Hardcoded gebruikers (kan later naar database)
USERS = {
    'admin': generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123'))
}

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and check_password_hash(USERS[username], password):
            user = User(username)
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Ongeldige gebruikersnaam of wachtwoord', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Globale variabele voor scraper status
scraper_status = {
    'running': False,
    'output': [],
    'companies_count': 0,
    'error': None
}

def run_scraper_thread(scraper_type, url, csv_file, excel_file, load_existing):
    """Voer scraper uit in aparte thread."""
    global scraper_status
    
    scraper_status['running'] = True
    scraper_status['output'] = []
    scraper_status['error'] = None
    
    try:
        # Redirect output naar status
        import sys
        from io import StringIO
        
        class OutputCapture:
            def __init__(self):
                self.buffer = []
            
            def write(self, text):
                self.buffer.append(text)
                scraper_status['output'].append(text)
                # Beperk output tot laatste 1000 regels
                if len(scraper_status['output']) > 1000:
                    scraper_status['output'] = scraper_status['output'][-1000:]
            
            def flush(self):
                pass
        
        old_stdout = sys.stdout
        sys.stdout = OutputCapture()
        
        try:
            if scraper_type == 'trustoo':
                companies = run_trustoo_scraper(
                    target_url=url,
                    csv_filename=csv_file,
                    excel_filename=excel_file,
                    load_existing=load_existing,
                    headless=True,  # Headless voor server
                    max_additional_pages=None
                )
            else:  # werkspot
                companies = run_werkspot_scraper(
                    target_url=url,
                    csv_filename=csv_file,
                    excel_filename=excel_file,
                    load_existing=load_existing,
                    headless=True,  # Headless voor server
                    max_additional_pages=None
                )
            
            scraper_status['companies_count'] = len(companies)
            scraper_status['output'].append(f"\n\n✅ Scrapen succesvol voltooid!\n📊 Totaal: {len(companies)} bedrijven\n")
        finally:
            sys.stdout = old_stdout
            
    except Exception as e:
        scraper_status['error'] = str(e)
        scraper_status['output'].append(f"\n\n❌ Fout opgetreden: {str(e)}\n")
    finally:
        scraper_status['running'] = False

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
@login_required
def start_scraper():
    global scraper_status
    
    if scraper_status['running']:
        return jsonify({'error': 'Scraper draait al'}), 400
    
    data = request.json
    scraper_type = data.get('scraper_type', 'trustoo')
    url = data.get('url', '')
    mode = data.get('mode', 'new')
    csv_file = data.get('csv_file') or None
    excel_file = data.get('excel_file') or None
    
    # Validatie
    if not url or not url.startswith('http'):
        return jsonify({'error': 'Ongeldige URL'}), 400
    
    load_existing = (mode == 'continue')
    
    # Start scraper in thread
    thread = threading.Thread(
        target=run_scraper_thread,
        args=(scraper_type, url, csv_file, excel_file, load_existing),
        daemon=True
    )
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
@login_required
def stop_scraper():
    global scraper_status
    
    # Note: Dit is een zachte stop - de scraper moet zelf stoppen
    scraper_status['running'] = False
    return jsonify({'status': 'stop_requested'})

@app.route('/api/status', methods=['GET'])
@login_required
def get_status():
    global scraper_status
    
    return jsonify({
        'running': scraper_status['running'],
        'output': ''.join(scraper_status['output'][-100:]),  # Laatste 100 regels
        'companies_count': scraper_status['companies_count'],
        'error': scraper_status['error']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

