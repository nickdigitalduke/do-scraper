from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import os
import threading
import json
import glob
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
    'stop_requested': False,  # Flag voor stoppen
    'output': [],
    'companies_count': 0,
    'error': None,
    'csv_file': None,
    'excel_file': None,
    'scraper_instance': None,  # Houd scraper instance bij voor direct stoppen
    'last_scraper_instance': None  # Houd laatste scraper instance bij voor bestanden
}

def run_scraper_thread(scraper_type, url, csv_file, excel_file, load_existing, title=None):
    """Voer scraper uit in aparte thread."""
    global scraper_status
    
    scraper_status['running'] = True
    scraper_status['stop_requested'] = False
    scraper_status['output'] = []
    scraper_status['error'] = None
    scraper_status['csv_file'] = None
    scraper_status['excel_file'] = None
    scraper_status['scraper_instance'] = None
    
    # Opslaan van parameters voor gebruik bij stop
    scraper_status['_csv_file'] = csv_file
    scraper_status['_excel_file'] = excel_file
    scraper_status['_title'] = title
    
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
            # Maak een stop callback functie die de scraper kan gebruiken
            def should_stop():
                return scraper_status.get('stop_requested', False)
            
            scraper_instance = None
            
            if scraper_type == 'trustoo':
                from script import TrustooPreciseScraper
                # Maak scraper instance direct aan
                scraper_instance = TrustooPreciseScraper(
                    headless=False,  # Lokaal: niet headless zodat gebruiker kan zien wat er gebeurt
                    load_existing=load_existing,
                    stop_callback=should_stop
                )
                # OPSLAAN IN STATUS VOOR DIRECTE TOEGANG
                scraper_status['scraper_instance'] = scraper_instance
                
                try:
                    # Scrape de pagina
                    # resume_from_checkpoint moet alleen True zijn als load_existing True is
                    resume_from_checkpoint = load_existing
                    companies = scraper_instance.scrape_category_page(url, max_additional_pages=None, resume_from_checkpoint=resume_from_checkpoint)
                    
                    # Check of gestopt is
                    was_stopped = scraper_instance._was_stopped or should_stop()
                    
                    if was_stopped:
                        print(f"\n⚠️ Scrapen gestopt door gebruiker")
                    else:
                        print(f"\n✅ Scrapen voltooid")
                    
                    print(f"📊 Totaal verzameld: {len(companies)} bedrijven")
                    
                    # Genereer bestandsnamen
                    output_dir = "scrapes"
                    if title:
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_title = safe_title.replace(' ', '_')
                        output_dir = os.path.join("scrapes", safe_title)
                    os.makedirs(output_dir, exist_ok=True)
                    
                    base_name = title.replace(' ', '_').lower() if title else "trustoo_scrape"
                    base_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-'))
                    
                    # Gebruik altijd de titel in de bestandsnaam, tenzij expliciet een andere naam is opgegeven
                    if not csv_file:
                        csv_path = os_module.path.join(output_dir, f"{base_name}.csv")
                    else:
                        # Als er een custom naam is, gebruik die maar plaats in de juiste directory
                        csv_filename = os_module.path.basename(csv_file)
                        # Als de custom naam geen extensie heeft, voeg .csv toe
                        if not csv_filename.endswith('.csv'):
                            csv_filename = f"{csv_filename}.csv"
                        csv_path = os_module.path.join(output_dir, csv_filename)
                        
                    if not excel_file:
                        excel_path = os_module.path.join(output_dir, f"{base_name}.xlsx")
                    else:
                        # Als er een custom naam is, gebruik die maar plaats in de juiste directory
                        excel_filename = os_module.path.basename(excel_file)
                        # Als de custom naam geen extensie heeft, voeg .xlsx toe
                        if not excel_filename.endswith('.xlsx'):
                            excel_filename = f"{excel_filename}.xlsx"
                        excel_path = os_module.path.join(output_dir, excel_filename)
                    
                    # Opslaan - gebruik absolute paden
                    abs_csv_path = os.path.abspath(csv_path)
                    abs_excel_path = os.path.abspath(excel_path)
                    
                    print(f"💾 Bestanden opslaan naar: {abs_csv_path}")
                    scraper_instance.save_to_csv(abs_csv_path, silent=True)
                    scraper_instance.save_to_excel(abs_excel_path, silent=True)
                    
                    # Verifieer dat bestanden zijn aangemaakt
                    if os.path.exists(abs_csv_path):
                        file_size = os.path.getsize(abs_csv_path)
                        print(f"✅ CSV bestand aangemaakt: {abs_csv_path} ({file_size} bytes)")
                    else:
                        print(f"⚠️ CSV bestand NIET aangemaakt: {abs_csv_path}")
                    
                    if os.path.exists(abs_excel_path):
                        file_size = os.path.getsize(abs_excel_path)
                        print(f"✅ Excel bestand aangemaakt: {abs_excel_path} ({file_size} bytes)")
                    else:
                        print(f"⚠️ Excel bestand NIET aangemaakt: {abs_excel_path}")
                    
                    print(f"✅ {len(companies)} bedrijven opgeslagen")
                    
                    scraper_status['companies_count'] = len(companies)
                    scraper_status['csv_file'] = csv_path
                    scraper_status['excel_file'] = excel_path
                    
                finally:
                    # Sluit browser
                    scraper_instance.close()
                    scraper_status['scraper_instance'] = None
                    
            else:  # werkspot
                companies, csv_path, excel_path = run_werkspot_scraper(
                    target_url=url,
                    csv_filename=csv_file,
                    excel_filename=excel_file,
                    load_existing=load_existing,
                    headless=False,  # Lokaal: niet headless
                    max_additional_pages=None,
                    title=title,
                    stop_callback=should_stop
                )
                
                scraper_status['companies_count'] = len(companies)
                scraper_status['csv_file'] = csv_path
                scraper_status['excel_file'] = excel_path
            
            if scraper_status.get('stop_requested', False):
                scraper_status['output'].append(f"\n\n⚠️ Scrapen gestopt door gebruiker\n📊 Totaal verzameld: {len(companies)} bedrijven\n💾 Bestanden opgeslagen in: {csv_path}\n")
            else:
                scraper_status['output'].append(f"\n\n✅ Scrapen succesvol voltooid!\n📊 Totaal: {len(companies)} bedrijven\n💾 Bestanden opgeslagen in: {csv_path}\n")
        finally:
            sys.stdout = old_stdout
            
    except Exception as e:
        # Check of dit een stop request is
        is_stop_request = "STOP_REQUESTED" in str(e) or scraper_status.get('stop_requested', False)
        
        if is_stop_request:
            scraper_status['output'].append(f"\n\n⚠️ Scrapen gestopt door gebruiker\n")
        else:
            scraper_status['error'] = str(e)
            scraper_status['output'].append(f"\n\n❌ Fout opgetreden: {str(e)}\n")
        
        # Probeer nog steeds op te slaan wat we hebben
        if scraper_status.get('companies_count', 0) > 0:
            if is_stop_request:
                scraper_status['output'].append(f"💾 Bestanden worden opgeslagen...\n")
            else:
                scraper_status['output'].append(f"⚠️ Probeer bestanden te downloaden met wat er verzameld is...\n")
    finally:
        scraper_status['running'] = False
        
        # ALTIJD proberen bestanden te vinden, ook als er een fout was of gestopt is
        try:
            import glob
            import os
            
            # Zoek naar meest recente bestanden in scrapes directory
            csv_files = glob.glob("scrapes/**/*.csv", recursive=True)
            excel_files = glob.glob("scrapes/**/*.xlsx", recursive=True)
            
            # Sorteer op modificatietijd (meest recent eerst)
            if csv_files:
                csv_files.sort(key=os.path.getmtime, reverse=True)
                # Gebruik meest recente CSV als we er nog geen hebben OF als deze nieuwer is
                if not scraper_status.get('csv_file') or (csv_files and os.path.getmtime(csv_files[0]) > os.path.getmtime(scraper_status.get('csv_file', ''))):
                    scraper_status['csv_file'] = csv_files[0]
            
            if excel_files:
                excel_files.sort(key=os.path.getmtime, reverse=True)
                # Gebruik meest recente Excel als we er nog geen hebben OF als deze nieuwer is
                if not scraper_status.get('excel_file') or (excel_files and os.path.getmtime(excel_files[0]) > os.path.getmtime(scraper_status.get('excel_file', ''))):
                    scraper_status['excel_file'] = excel_files[0]
            
            # Als we bestanden hebben gevonden, log dit
            if scraper_status.get('csv_file') or scraper_status.get('excel_file'):
                if scraper_status.get('stop_requested', False):
                    scraper_status['output'].append(f"✅ Bestanden gevonden en klaar voor download!\n")
        except Exception as e:
            scraper_status['output'].append(f"\n⚠️ Kon bestanden niet vinden: {str(e)}\n")
        
        # Zorg dat stop_requested wordt gereset voor volgende run
        scraper_status['stop_requested'] = False

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
    title = data.get('title') or None
    
    # Validatie
    if not url or not url.startswith('http'):
        return jsonify({'error': 'Ongeldige URL'}), 400
    
    load_existing = (mode == 'continue')
    
    # Start scraper in thread
    thread = threading.Thread(
        target=run_scraper_thread,
        args=(scraper_type, url, csv_file, excel_file, load_existing, title),
        daemon=True
    )
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
@login_required
def stop_scraper():
    global scraper_status
    
    # Zet stop flag DIRECT - dit is het belangrijkste!
    scraper_status['stop_requested'] = True
    
    # Voeg bericht toe aan output
    scraper_status['output'].append("\n🛑 STOP AANGEVRAAGD - Script stopt NU...\n")
    
    # DIRECT DE SCRAPER STOPPEN EN BESTANDEN OPSLAAN
    scraper_instance = scraper_status.get('scraper_instance')
    if scraper_instance:
        try:
            print("🛑 FORCE STOP aangeroepen vanuit stop endpoint")
            
            # Zet stop flag in scraper zelf
            scraper_instance._was_stopped = True
            
            # Sla bestanden direct op VOORDAT browser sluit
            if len(scraper_instance.companies_data) > 0:
                try:
                    # Gebruik globale os module (niet lokaal importeren)
                    import os as os_module
                    
                    # Genereer bestandsnamen
                    output_dir = "scrapes"
                    title = scraper_status.get('_title')
                    if title:
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_title = safe_title.replace(' ', '_')
                        output_dir = os_module.path.join("scrapes", safe_title)
                    os_module.makedirs(output_dir, exist_ok=True)
                    
                    base_name = title.replace(' ', '_').lower() if title else "trustoo_scrape"
                    base_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-'))
                    
                    csv_file = scraper_status.get('_csv_file')
                    excel_file = scraper_status.get('_excel_file')
                    
                    # Gebruik altijd de titel in de bestandsnaam, tenzij expliciet een andere naam is opgegeven
                    if not csv_file:
                        csv_path = os_module.path.join(output_dir, f"{base_name}.csv")
                    else:
                        # Als er een custom naam is, gebruik die maar plaats in de juiste directory
                        csv_filename = os_module.path.basename(csv_file)
                        # Als de custom naam geen extensie heeft, voeg .csv toe
                        if not csv_filename.endswith('.csv'):
                            csv_filename = f"{csv_filename}.csv"
                        csv_path = os_module.path.join(output_dir, csv_filename)
                        
                    if not excel_file:
                        excel_path = os_module.path.join(output_dir, f"{base_name}.xlsx")
                    else:
                        # Als er een custom naam is, gebruik die maar plaats in de juiste directory
                        excel_filename = os_module.path.basename(excel_file)
                        # Als de custom naam geen extensie heeft, voeg .xlsx toe
                        if not excel_filename.endswith('.xlsx'):
                            excel_filename = f"{excel_filename}.xlsx"
                        excel_path = os_module.path.join(output_dir, excel_filename)
                    
                    # BELANGRIJK: Gebruik de data uit scraper_instance.companies_data
                    # Dit bevat ALLE verzamelde data, niet alleen de eerste batch
                    num_companies = len(scraper_instance.companies_data)
                    
                    # Sla op - gebruik absolute paden
                    abs_csv_path = os_module.path.abspath(csv_path)
                    abs_excel_path = os_module.path.abspath(excel_path)
                    
                    print(f"💾 Opslaan naar: {abs_csv_path}")
                    scraper_instance.save_to_csv(abs_csv_path, silent=True)
                    scraper_instance.save_to_excel(abs_excel_path, silent=True)
                    
                    # Verifieer dat bestanden zijn aangemaakt
                    if os_module.path.exists(abs_csv_path):
                        print(f"✅ CSV bestand aangemaakt: {abs_csv_path}")
                    else:
                        print(f"⚠️ CSV bestand NIET aangemaakt: {abs_csv_path}")
                    
                    if os_module.path.exists(abs_excel_path):
                        print(f"✅ Excel bestand aangemaakt: {abs_excel_path}")
                    else:
                        print(f"⚠️ Excel bestand NIET aangemaakt: {abs_excel_path}")
                    
                    scraper_status['csv_file'] = csv_path
                    scraper_status['excel_file'] = excel_path
                    scraper_status['companies_count'] = num_companies
                    scraper_status['output'].append(f"✅ {num_companies} bedrijven opgeslagen!\n")
                    scraper_status['output'].append(f"📁 CSV: {csv_path}\n")
                    scraper_status['output'].append(f"📁 Excel: {excel_path}\n")
                except Exception as save_err:
                    import traceback
                    scraper_status['output'].append(f"⚠️ Fout bij opslaan: {save_err}\n")
                    scraper_status['output'].append(f"Traceback: {traceback.format_exc()}\n")
            
            # SLUIT BROWSER DIRECT - FORCEER!
            try:
                if scraper_instance.driver:
                    scraper_instance.driver.quit()
                    scraper_status['output'].append("🔒 Browser geforceerd gesloten\n")
            except Exception as close_err:
                scraper_status['output'].append(f"⚠️ Fout bij sluiten browser: {close_err}\n")
                # Probeer nog een keer met force
                try:
                    import signal
                    import psutil
                    import os
                    # Kill alle Chrome processen die door deze scraper zijn gestart
                    for proc in psutil.process_iter(['pid', 'name']):
                        if 'chrome' in proc.info['name'].lower():
                            try:
                                proc.kill()
                            except:
                                pass
                except:
                    pass
                    
        except Exception as e:
            scraper_status['output'].append(f"⚠️ Fout bij stoppen: {str(e)}\n")
            import traceback
            scraper_status['output'].append(f"Traceback: {traceback.format_exc()}\n")
            # Probeer nog steeds bestanden te vinden
            try:
                import glob
                import os
                csv_files = glob.glob("scrapes/**/*.csv", recursive=True)
                excel_files = glob.glob("scrapes/**/*.xlsx", recursive=True)
                
                if csv_files:
                    csv_files.sort(key=os.path.getmtime, reverse=True)
                    scraper_status['csv_file'] = csv_files[0]
                if excel_files:
                    excel_files.sort(key=os.path.getmtime, reverse=True)
                    scraper_status['excel_file'] = excel_files[0]
            except:
                pass
    
    return jsonify({
        'status': 'stop_requested',
        'csv_file': scraper_status.get('csv_file'),
        'excel_file': scraper_status.get('excel_file'),
        'companies_count': scraper_status.get('companies_count', 0)
    })

@app.route('/api/status', methods=['GET'])
@login_required
def get_status():
    global scraper_status
    
    return jsonify({
        'running': scraper_status['running'],
        'output': ''.join(scraper_status['output'][-100:]),  # Laatste 100 regels
        'companies_count': scraper_status['companies_count'],
        'error': scraper_status['error'],
        'csv_file': scraper_status['csv_file'],
        'excel_file': scraper_status['excel_file']
    })

@app.route('/api/download/<path:filename>')
@login_required
def download_file(filename):
    """Download een bestand."""
    from flask import send_file
    import os
    
    # Beveiliging: alleen bestanden uit scrapes map
    if not filename.startswith('scrapes/'):
        return jsonify({'error': 'Ongeldig pad'}), 400
    
    file_path = os.path.join(os.getcwd(), filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'Bestand niet gevonden'}), 404
    
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    # Op Railway gebruik PORT, lokaal gebruik 5001 (5000 wordt gebruikt door macOS AirPlay)
    port = int(os.environ.get('PORT', 5001))
    # Op Railway moet debug=False zijn
    app.run(host='0.0.0.0', port=port, debug=False)

