import time
import random
import re
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class WerkspotScraper:
    """Werkspot scraper - volledig gescheiden van Trustoo code."""
    
    def __init__(self, headless=True, load_existing=True, stop_callback=None):
        """Initialiseer de scraper voor Werkspot."""
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # Railway/Server specifieke opties
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # Blokkeer locatie-detectie
        options.add_argument('--disable-geolocation')
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.notifications": 2
        })
        
        # Gebruik webdriver-manager voor automatische Chrome driver installatie
        # Op Railway, gebruik chromium uit nixpacks
        chrome_binary = os.environ.get('CHROME_BIN')
        if chrome_binary and os.path.exists(chrome_binary):
            options.binary_location = chrome_binary
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.companies_data = []
        
        # OPTIMALISATIE: Houd sets bij als instance variabelen
        self.existing_urls = set()
        self.existing_keys = set()
        
        # Checkpoint voor hervatten
        self.checkpoint_clicks = 0
        
        # Stop callback functie
        self.stop_callback = stop_callback
        
        # Flag om bij te houden of we gestopt zijn
        self._was_stopped = False
        
        # Laad bestaande data als die er is
        if load_existing:
            self.load_existing_data()
        
        # Mask automation
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def load_existing_data(self, csv_file="werkspot_elektriciens.csv", excel_file="werkspot_elektriciens.xlsx"):
        """Laad bestaande data vanuit CSV of Excel om te hervatten."""
        try:
            # Probeer eerst CSV
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file, encoding='utf-8-sig')
                if not df.empty:
                    self.companies_data = df.to_dict('records')
                    # Vul de sets met bestaande data
                    for company in self.companies_data:
                        if company.get('ProfielURL'):
                            self.existing_urls.add(company['ProfielURL'])
                        naam = company.get('Naam', '') or ''
                        adres = company.get('Adres', '') or ''
                        if naam or adres:
                            self.existing_keys.add((naam, adres))
                    print(f"✅ {len(self.companies_data)} bestaande bedrijven geladen vanuit {csv_file}")
                    if len(self.companies_data) > 0:
                        last_company = self.companies_data[-1]
                        last_name = last_company.get('Naam', 'Onbekend')[:50]
                        print(f"   Laatste bedrijf: {last_name}")
                    return
        except Exception as e:
            print(f"⚠️  Kon CSV niet laden: {e}")
        
        try:
            # Fallback naar Excel
            if os.path.exists(excel_file):
                df = pd.read_excel(excel_file)
                if not df.empty:
                    self.companies_data = df.to_dict('records')
                    # Vul de sets met bestaande data
                    for company in self.companies_data:
                        if company.get('ProfielURL'):
                            self.existing_urls.add(company['ProfielURL'])
                        naam = company.get('Naam', '') or ''
                        adres = company.get('Adres', '') or ''
                        if naam or adres:
                            self.existing_keys.add((naam, adres))
                    print(f"✅ {len(self.companies_data)} bestaande bedrijven geladen vanuit {excel_file}")
                    if len(self.companies_data) > 0:
                        last_company = self.companies_data[-1]
                        last_name = last_company.get('Naam', 'Onbekend')[:50]
                        print(f"   Laatste bedrijf: {last_name}")
        except Exception as e:
            print(f"⚠️  Kon Excel niet laden: {e}")
    
    def save_checkpoint(self, clicks):
        """Sla checkpoint op (aantal klikken)."""
        self.checkpoint_clicks = clicks
        try:
            with open("werkspot_checkpoint.txt", "w") as f:
                f.write(str(clicks))
        except:
            pass
    
    def load_checkpoint(self):
        """Laad checkpoint (aantal klikken)."""
        try:
            if os.path.exists("werkspot_checkpoint.txt"):
                with open("werkspot_checkpoint.txt", "r") as f:
                    clicks = int(f.read().strip())
                    self.checkpoint_clicks = clicks
                    print(f"📌 Checkpoint geladen: was gebleven bij {clicks} klikken")
                    return clicks
        except:
            pass
        return 0
    
    def extract_company_info(self, company_element):
        """Haal gegevens uit een Werkspot bedrijfsblok."""
        try:
            # 1. Bedrijfsnaam
            name = "Niet gevonden"
            try:
                name_element = company_element.find_element(By.CSS_SELECTOR, "h2, h3, .company-name, [class*='name']")
                name = name_element.text.strip()
            except NoSuchElementException:
                # Probeer alternatieve selectors
                try:
                    name_element = company_element.find_element(By.XPATH, ".//a[contains(@href, '/profiel/')]")
                    name = name_element.text.strip()
                except:
                    pass
            
            # 2. Adres
            address = "Niet gevonden"
            try:
                address_elements = company_element.find_elements(By.CSS_SELECTOR, "[class*='address'], [class*='location'], .address")
                if address_elements:
                    address = address_elements[0].text.strip()
                else:
                    # Probeer tekst met komma (adres format)
                    address_elements = company_element.find_elements(By.XPATH, ".//*[contains(text(), ',')]")
                    for elem in address_elements:
                        text = elem.text.strip()
                        if ',' in text and len(text) > 5:
                            address = text
                            break
            except:
                pass
            
            # 3. Telefoonnummer
            phone = "Niet vermeld"
            try:
                phone_elements = company_element.find_elements(By.CSS_SELECTOR, "[class*='phone'], [class*='tel'], a[href^='tel:']")
                for elem in phone_elements:
                    text = elem.text.strip() or elem.get_attribute('href', '').replace('tel:', '')
                    if any(char.isdigit() for char in text) and len(text.replace(' ', '').replace('-', '')) >= 8:
                        phone = text
                        break
            except:
                pass
            
            # 4. Rating/Score
            rating = "N/A"
            try:
                rating_elements = company_element.find_elements(By.CSS_SELECTOR, "[class*='rating'], [class*='score'], [class*='star']")
                for elem in rating_elements:
                    text = elem.text.strip()
                    # Zoek naar getal met punt of komma (bijv. 4.5 of 4,5)
                    match = re.search(r'(\d+[.,]\d+|\d+)', text)
                    if match:
                        rating = match.group(1).replace(',', '.')
                        break
            except:
                pass
            
            # 5. Aantal reviews
            num_reviews = "0"
            try:
                review_elements = company_element.find_elements(By.CSS_SELECTOR, "[class*='review'], [class*='review-count']")
                for elem in review_elements:
                    text = elem.text.strip()
                    # Zoek naar getal
                    match = re.search(r'(\d+)', text)
                    if match:
                        num_reviews = match.group(1)
                        break
            except:
                pass
            
            # 6. Link naar profiel
            profile_url = ""
            try:
                link_elements = company_element.find_elements(By.CSS_SELECTOR, "a[href*='/profiel/'], a[href*='/bedrijf/']")
                for link in link_elements:
                    href = link.get_attribute('href')
                    if href and ('/profiel/' in href or '/bedrijf/' in href):
                        profile_url = href
                        break
            except:
                pass
            
            # 7. Beschrijving
            description = ""
            try:
                desc_elements = company_element.find_elements(By.CSS_SELECTOR, "[class*='description'], [class*='bio'], p")
                if desc_elements:
                    description = desc_elements[0].text.strip()[:200]
            except:
                pass
            
            return {
                'Naam': name,
                'Adres': address,
                'Telefoon': phone,
                'Rating': rating,
                'AantalReviews': num_reviews,
                'ProfielURL': profile_url,
                'Beschrijving': description[:200] + "..." if len(description) > 200 else description
            }
        except Exception as e:
            print(f"   ⚠️  Fout bij extraheren bedrijfsinfo: {str(e)[:50]}")
            return {
                'Naam': "Fout",
                'Adres': "",
                'Telefoon': "",
                'Rating': "",
                'AantalReviews': "",
                'ProfielURL': "",
                'Beschrijving': ""
            }
    
    def accept_cookies(self):
        """Accepteer cookie melding."""
        try:
            cookie_selectors = [
                "button:contains('Accepteren')",
                "button:contains('Akkoord')",
                "button:contains('Accepteer')",
                "[id*='cookie'] button",
                "[class*='cookie'] button",
                "[data-testid*='cookie'] button"
            ]
            
            for selector in cookie_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        if btn.is_displayed():
                            btn.click()
                            print("Cookies geaccepteerd")
                            time.sleep(1)
                            return
                except:
                    continue
        except Exception as e:
            pass  # Geen cookie melding gevonden
    
    def scrape_category_page(self, url, max_additional_pages=None, save_interval=10, resume_from_checkpoint=True):
        """Scrape een Werkspot categoriepagina."""
        # Navigeer naar de pagina
        self.driver.get(url)
        
        # Accepteer cookies
        self.accept_cookies()
        
        # Wacht tot pagina geladen is
        time.sleep(3)
        
        # Eerst de initiële bedrijven verzamelen
        initial_count = len(self.companies_data)
        self._collect_companies_from_page(silent=True)
        
        clicks = 0
        if resume_from_checkpoint:
            clicks = self.load_checkpoint()
            if clicks > 0:
                # Snel doorklikken zonder te verzamelen (stil)
                for i in range(clicks):
                    try:
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        buttons = self.driver.find_elements(
                            By.XPATH, 
                            "//button[contains(text(), 'Meer') or contains(text(), 'Laad') or contains(text(), 'Toon')]"
                        )
                        for btn in buttons:
                            if btn.is_displayed() and btn.is_enabled():
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(2)
                                break
                    except:
                        pass
        
        consecutive_failures = 0
        max_failures = 5
        
        while (max_additional_pages is None or clicks < max_additional_pages) and consecutive_failures < max_failures:
            # Check of stoppen is aangevraagd
            if self.stop_callback and self.stop_callback():
                print(f"\n⚠️ Stop aangevraagd door gebruiker...")
                print(f"   📊 Tot nu toe verzameld: {len(self.companies_data)} bedrijven")
                print(f"   💾 Bestanden worden opgeslagen...")
                self._was_stopped = True
                break
            
            try:
                # Scroll naar beneden
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1, 2))
                
                # Zoek de "Meer" of "Laad meer" knop
                show_more_button = None
                try:
                    buttons = self.driver.find_elements(
                        By.XPATH, 
                        "//button[contains(text(), 'Meer') or contains(text(), 'Laad') or contains(text(), 'Toon')]"
                    )
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            show_more_button = btn
                            break
                except Exception as e:
                    pass
                
                if not show_more_button:
                    print(f"\n✅ Geen 'Meer resultaten' knop meer gevonden na {clicks} klikken.")
                    print(f"   📊 Totaal aantal bedrijven verzameld: {len(self.companies_data)}")
                    # Laatste keer verzamelen
                    print(f"   🔍 Laatste scan voor alle bedrijven...")
                    self._collect_companies_from_page()
                    print(f"   📊 Eindtotaal: {len(self.companies_data)} bedrijven")
                    break
                
                # Klik op de knop
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                        show_more_button
                    )
                    time.sleep(random.uniform(0.5, 1))
                    self.driver.execute_script("arguments[0].click();", show_more_button)
                except Exception as e:
                    try:
                        show_more_button.click()
                    except Exception as e2:
                        consecutive_failures += 1
                        continue
                
                clicks += 1
                consecutive_failures = 0
                
                # Sla checkpoint op (stil)
                self.save_checkpoint(clicks)
                
                # Wacht LANGER tot content laadt (VOORZICHTIG - voorkom IP blok!)
                time.sleep(random.uniform(8, 12))
                try:
                    self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                except:
                    pass
                
                # Extra wachttijd voor dynamische content (VOORZICHTIG!)
                time.sleep(random.uniform(3, 5))
                
                # Check opnieuw of stoppen is aangevraagd VOORDAT we verzamelen
                if self.stop_callback and self.stop_callback():
                    print(f"\n⚠️ Stop aangevraagd")
                    print(f"📊 Tot nu toe verzameld: {len(self.companies_data)} bedrijven")
                    print(f"💾 Bestanden worden opgeslagen...")
                    self._was_stopped = True
                    break
                
                # Verzamel nieuwe bedrijven
                new_count_before = len(self.companies_data)
                self._collect_companies_from_page(silent=True)
                new_count_after = len(self.companies_data)
                new_companies = new_count_after - new_count_before
                
                # Check opnieuw na verzamelen
                if self.stop_callback and self.stop_callback():
                    print(f"\n⚠️ Stop aangevraagd")
                    print(f"📊 Tot nu toe verzameld: {len(self.companies_data)} bedrijven")
                    print(f"💾 Bestanden worden opgeslagen...")
                    self._was_stopped = True
                    if len(self.companies_data) > 0:
                        try:
                            temp_csv = f"scrapes/temp_stopped_{int(time.time())}.csv"
                            temp_excel = f"scrapes/temp_stopped_{int(time.time())}.xlsx"
                            os.makedirs("scrapes", exist_ok=True)
                            self.save_to_csv(temp_csv, silent=True)
                            self.save_to_excel(temp_excel, silent=True)
                            print(f"✅ Bestanden opgeslagen")
                        except Exception as save_err:
                            print(f"⚠️ Fout bij opslaan: {save_err}")
                    break
                
                # Alleen tonen als er nieuwe bedrijven zijn gevonden
                if new_companies > 0:
                    print(f"✅ {new_companies} nieuwe bedrijven gevonden (totaal: {new_count_after})")
                
                # Tussentijds opslaan (stil)
                if len(self.companies_data) > 0 and len(self.companies_data) % save_interval == 0:
                    self.save_to_excel(silent=True)
                    self.save_to_csv(silent=True)
                
            except StaleElementReferenceException:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print(f"\n❌ Te veel fouten, stoppen")
                    break
                time.sleep(random.uniform(2, 3))
                continue
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print(f"\n❌ Te veel fouten, stoppen")
                    break
                time.sleep(random.uniform(2, 3))
                continue
        
        return self.companies_data
    
    def _collect_companies_from_page(self, silent=False):
        """Verzamel bedrijven van de huidige pagina."""
        try:
            # BELANGRIJK: Scroll eerst naar beneden om te zorgen dat ALLE content geladen is
            try:
                # Scroll langzaam naar beneden om lazy loading te triggeren
                for i in range(5):
                    self.driver.execute_script(f"window.scrollTo(0, {(i+1) * 500});")
                    time.sleep(0.3)
                # Scroll naar beneden
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                # Scroll terug naar boven
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)
            except:
                pass
            
            # BELANGRIJK: Wacht even tot alle content geladen is
            time.sleep(1)
            
            # Zoek naar bedrijfscontainers - Werkspot gebruikt verschillende structuren
            # Probeer verschillende selectors
            company_containers = []
            
            # Strategie 1: Zoek naar cards/items met links naar profielen - probeer meerdere keren
            for attempt in range(3):
                try:
                    containers = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        "[class*='card'], [class*='item'], [class*='result'], [class*='company']"
                    )
                    # Filter alleen containers met links naar profielen
                    for container in containers:
                        try:
                            links = container.find_elements(By.CSS_SELECTOR, "a[href*='/profiel/'], a[href*='/bedrijf/']")
                            if links and container not in company_containers:
                                company_containers.append(container)
                        except:
                            pass
                    # Als we containers hebben gevonden en dit niet de laatste poging is, wacht even en scroll
                    if len(company_containers) > 0 and attempt < 2:
                        time.sleep(0.5)
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
                        time.sleep(0.5)
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                except:
                    pass
            
            # Strategie 2: Als geen containers gevonden, zoek direct naar links
            if not company_containers:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/profiel/'], a[href*='/bedrijf/']")
                    # Gebruik parent elementen als containers
                    for link in links:
                        try:
                            container = link.find_element(By.XPATH, "./ancestor::div[contains(@class, 'card') or contains(@class, 'item')]")
                            if container not in company_containers:
                                company_containers.append(container)
                        except:
                            # Gebruik link zelf als container
                            try:
                                if link not in company_containers:
                                    company_containers.append(link)
                            except:
                                pass
                except:
                    pass
            
            # Log hoeveel containers gevonden zijn
            if not silent:
                print(f"   📋 Gevonden {len(company_containers)} bedrijfscontainers op pagina")
            elif len(company_containers) > 0:
                print(f"   📋 Gevonden {len(company_containers)} bedrijfscontainers op pagina")
            
            added_count = 0
            skipped_count = 0
            
            for container in company_containers:
                # Check of stoppen is aangevraagd tijdens verzamelen
                if self.stop_callback and self.stop_callback():
                    break
                
                try:
                    company_info = self.extract_company_info(container)
                    
                    # Check of het een nieuw bedrijf is
                    is_new = False
                    
                    # Gebruik URL als primaire identifier
                    if company_info.get('ProfielURL') and company_info['ProfielURL']:
                        if company_info['ProfielURL'] not in self.existing_urls:
                            is_new = True
                    else:
                        # Als er geen URL is, gebruik naam+adres
                        naam = company_info.get('Naam', '') or ''
                        adres = company_info.get('Adres', '') or ''
                        key = (naam, adres)
                        
                        if key not in self.existing_keys and (naam or adres):
                            is_new = True
                    
                    if is_new:
                        self.companies_data.append(company_info)
                        # Update de sets direct
                        if company_info.get('ProfielURL'):
                            self.existing_urls.add(company_info['ProfielURL'])
                        naam = company_info.get('Naam', '') or ''
                        adres = company_info.get('Adres', '') or ''
                        if naam or adres:
                            self.existing_keys.add((naam, adres))
                        added_count += 1
                        
                        # Alleen tonen als niet silent
                        if not silent:
                            display_naam = company_info.get('Naam', 'Geen naam')[:50]
                            rating = company_info.get('Rating', 'N/A')
                            reviews = company_info.get('AantalReviews', '0')
                            print(f"✓ {display_naam} (Rating: {rating}, Reviews: {reviews})")
                    else:
                        skipped_count += 1
                    
                except StaleElementReferenceException:
                    skipped_count += 1
                    continue
                except Exception as e:
                    skipped_count += 1
                    continue
            
            # ALTIJD totaal tonen (ook als silent, maar alleen als er iets is gebeurd)
            if not silent:
                if added_count > 0:
                    print(f"📊 Toegevoegd: {added_count}, Overgeslagen: {skipped_count}, Totaal: {len(self.companies_data)}")
                elif skipped_count > 0:
                    print(f"⚠️  Alle {skipped_count} bedrijven waren duplicates, Totaal: {len(self.companies_data)}")
                elif len(company_containers) == 0:
                    print(f"⚠️  Geen bedrijfscontainers gevonden op pagina")
            elif added_count > 0 or skipped_count > 0:
                # Zelfs in silent mode, log als er activiteit was
                print(f"   📊 Verzameld: {added_count} nieuw, {skipped_count} duplicates, Totaal: {len(self.companies_data)}")
            elif len(company_containers) == 0:
                # Log ook als er geen containers zijn gevonden (ook in silent mode)
                print(f"   ⚠️  Geen bedrijfscontainers gevonden op pagina")
                    
        except Exception as e:
            print(f"   ⚠️  Fout bij verzamelen bedrijven: {str(e)[:80]}")
    
    def save_to_excel(self, filename="werkspot_elektriciens.xlsx", silent=False):
        """Sla gegevens op in Excel."""
        if not self.companies_data:
            if not silent:
                print("Geen gegevens om op te slaan.")
            return
        
        df = pd.DataFrame(self.companies_data)
        
        # Maak kolommen leesbaarder
        column_order = [
            'Naam', 'Adres', 'Telefoon', 'Rating', 'AantalReviews',
            'Beschrijving', 'ProfielURL'
        ]
        
        # Alleen kolommen die bestaan
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]
        
        df.to_excel(filename, index=False)
        if not silent:
            print(f"💾 {len(self.companies_data)} bedrijven opgeslagen in: {filename}")
        return filename
    
    def save_to_csv(self, filename="werkspot_elektriciens.csv", silent=False):
        """Sla gegevens op in CSV."""
        if not self.companies_data:
            if not silent:
                print("Geen gegevens om op te slaan.")
            return
        
        df = pd.DataFrame(self.companies_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        if not silent:
            print(f"💾 {len(self.companies_data)} bedrijven opgeslagen in: {filename}")
        return filename
    
    def close(self):
        """Sluit de browser."""
        if self.driver:
            self.driver.quit()
            print("Browser gesloten.")

def run_werkspot_scraper(target_url, csv_filename=None, excel_filename=None, load_existing=True, headless=False, max_additional_pages=None, title=None, stop_callback=None):
    """Voer de Werkspot scraper uit met gegeven parameters."""
    scraper = WerkspotScraper(headless=headless, load_existing=load_existing, stop_callback=stop_callback)
    
    try:
        # Scrape de pagina
        companies = scraper.scrape_category_page(target_url, max_additional_pages=max_additional_pages)
        
        # Check of gestopt is (via callback of via flag)
        was_stopped = scraper._was_stopped or (stop_callback and stop_callback())
        
        if was_stopped:
            print(f"\n⚠️ Scrapen gestopt door gebruiker")
        else:
            print(f"\n✅ Scrapen voltooid")
        
        print(f"📊 Totaal verzameld: {len(companies)} bedrijven")
        
        # Maak mapje aan als titel is opgegeven
        output_dir = "scrapes"
        if title:
            # Maak veilige mapnaam van titel
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')
            output_dir = os.path.join("scrapes", safe_title)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Genereer bestandsnamen
        base_name = title.replace(' ', '_').lower() if title else "werkspot_scrape"
        base_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-'))
        
        if not csv_filename:
            csv_filename = os.path.join(output_dir, f"{base_name}.csv")
        else:
            csv_filename = os.path.join(output_dir, os.path.basename(csv_filename))
            
        if not excel_filename:
            excel_filename = os.path.join(output_dir, f"{base_name}.xlsx")
        else:
            excel_filename = os.path.join(output_dir, os.path.basename(excel_filename))
        
        # Opslaan met aangepaste bestandsnamen indien opgegeven
        print("💾 Bestanden opslaan...")
        scraper.save_to_csv(csv_filename, silent=True)
        scraper.save_to_excel(excel_filename, silent=True)
        print(f"✅ {len(companies)} bedrijven opgeslagen")
        
        return companies, csv_filename, excel_filename
        
    except Exception as e:
        print(f"\n❌ Fout opgetreden: {e}")
        raise
    finally:
        scraper.close()

# 💡 HOOFDGEBRUIK
if __name__ == "__main__":
    import sys
    
    # Als er command line argumenten zijn, gebruik die
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        csv_file = sys.argv[2] if len(sys.argv) > 2 else None
        excel_file = sys.argv[3] if len(sys.argv) > 3 else None
        load_existing = sys.argv[4].lower() == 'true' if len(sys.argv) > 4 else True
        
        run_werkspot_scraper(target_url, csv_file, excel_file, load_existing)
    else:
        # Standaard gedrag
        scraper = WerkspotScraper(headless=False)
        
        try:
            target_url = "https://www.werkspot.nl/elektricien"  # Pas aan naar jouw URL
            
            print("=" * 60)
            print("WERKSPOT SCRAPER - ELEKTRICIENS")
            print("=" * 60)
            
            companies = scraper.scrape_category_page(target_url, max_additional_pages=None)
            
            print(f"\n✅ Scrapen voltooid!")
            print(f"📊 Totaal verzameld: {len(companies)} bedrijven")
            
            # Opslaan
            print("\n💾 Gegevens opslaan...")
            scraper.save_to_excel()
            scraper.save_to_csv()
            
        except Exception as e:
            print(f"\n❌ Fout opgetreden: {e}")
        finally:
            scraper.close()

