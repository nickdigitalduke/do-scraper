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
    
    def __init__(self, headless=True, load_existing=True):
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
        print(f"🚀 Werkspot scrapen gestart: {url}")
        
        # Navigeer naar de pagina
        self.driver.get(url)
        
        # Accepteer cookies
        self.accept_cookies()
        
        # Wacht tot pagina geladen is
        time.sleep(3)
        
        # Eerst de initiële bedrijven verzamelen
        print("\n📋 Stap 1: Initiële bedrijven verzamelen...")
        initial_count = len(self.companies_data)
        self._collect_companies_from_page()
        
        # Toon info over bestaande data als we hervatten
        if resume_from_checkpoint and initial_count > 0:
            print(f"📊 Huidige status: {initial_count} bedrijven al in bestand")
            if self.companies_data:
                last_company = self.companies_data[-1]
                last_name = last_company.get('Naam', 'Onbekend')[:50]
                print(f"   Laatste bedrijf in bestand: {last_name}")
        
        # Klik op 'Toon meer' of 'Laad meer' knoppen
        print(f"\n🔄 Stap 2: Meer resultaten laden...")
        if max_additional_pages is None:
            print("   (Onbeperkt doorgaan tot alle resultaten geladen zijn)")
        
        clicks = 0
        if resume_from_checkpoint:
            clicks = self.load_checkpoint()
            if clicks > 0:
                print(f"\n🔄 Hervatten vanaf checkpoint:")
                print(f"   📍 Was gebleven bij: {clicks} klikken")
                print(f"   📊 Bestaande bedrijven in bestand: {len(self.companies_data)}")
                print(f"   ⏩ Snel doorklikken naar checkpoint...")
                # Snel doorklikken zonder te verzamelen
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
                print(f"✅ Bij checkpoint aangekomen, nu verder scrapen vanaf hier...")
                print(f"   (Nieuwe bedrijven worden toegevoegd, bestaande worden automatisch overgeslagen)\n")
        
        consecutive_failures = 0
        max_failures = 5
        
        while (max_additional_pages is None or clicks < max_additional_pages) and consecutive_failures < max_failures:
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
                print(f"\n   ✅ Klik {clicks}: Meer resultaten geladen...")
                
                # Sla checkpoint op
                self.save_checkpoint(clicks)
                
                # Wacht tot content laadt
                time.sleep(random.uniform(5, 7))
                try:
                    self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                except:
                    pass
                
                # Extra wachttijd voor dynamische content
                time.sleep(random.uniform(2, 3))
                
                # Verzamel nieuwe bedrijven
                new_count_before = len(self.companies_data)
                self._collect_companies_from_page()
                new_count_after = len(self.companies_data)
                new_companies = new_count_after - new_count_before
                
                if new_companies > 0:
                    print(f"   ✅ {new_companies} nieuwe bedrijven gevonden (totaal: {new_count_after})")
                else:
                    print(f"   ⚠️  Geen nieuwe bedrijven gevonden na klik {clicks}")
                
                # Tussentijds opslaan
                if len(self.companies_data) > 0 and len(self.companies_data) % save_interval == 0:
                    print(f"   💾 Tussentijds opslaan ({len(self.companies_data)} bedrijven)...")
                    self.save_to_excel(silent=True)
                    self.save_to_csv(silent=True)
                
            except StaleElementReferenceException:
                consecutive_failures += 1
                print(f"   ⚠️  Stale element (poging {consecutive_failures}/{max_failures}), opnieuw proberen...")
                time.sleep(random.uniform(2, 3))
                continue
            except Exception as e:
                consecutive_failures += 1
                print(f"   ⚠️  Fout (poging {consecutive_failures}/{max_failures}): {str(e)[:80]}")
                if consecutive_failures >= max_failures:
                    print("   ❌ Te veel fouten, stoppen met klikken.")
                    break
                time.sleep(random.uniform(2, 3))
                continue
        
        print(f"\n✅ Totaal {clicks} extra ladingen uitgevoerd")
        return self.companies_data
    
    def _collect_companies_from_page(self):
        """Verzamel bedrijven van de huidige pagina."""
        try:
            # Zoek naar bedrijfscontainers - Werkspot gebruikt verschillende structuren
            # Probeer verschillende selectors
            company_containers = []
            
            # Strategie 1: Zoek naar cards/items met links naar profielen
            try:
                containers = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "[class*='card'], [class*='item'], [class*='result'], [class*='company']"
                )
                # Filter alleen containers met links naar profielen
                for container in containers:
                    try:
                        links = container.find_elements(By.CSS_SELECTOR, "a[href*='/profiel/'], a[href*='/bedrijf/']")
                        if links:
                            company_containers.append(container)
                    except:
                        pass
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
            
            print(f"   🔍 Gevonden containers op pagina: {len(company_containers)}")
            
            added_count = 0
            skipped_count = 0
            
            for container in company_containers:
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
                        
                        # Toon elk gevonden bedrijf
                        display_naam = company_info.get('Naam', 'Geen naam')[:50]
                        rating = company_info.get('Rating', 'N/A')
                        reviews = company_info.get('AantalReviews', '0')
                        print(f"   ✓ {display_naam} (Rating: {rating}, Reviews: {reviews})")
                    else:
                        skipped_count += 1
                    
                except StaleElementReferenceException:
                    skipped_count += 1
                    continue
                except Exception as e:
                    skipped_count += 1
                    continue
            
            # Toon alleen toegevoegde en totaal, geen overgeslagen berichten
            print(f"   📊 Toegevoegd: {added_count}, Totaal: {len(self.companies_data)}")
                    
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

def run_werkspot_scraper(target_url, csv_filename=None, excel_filename=None, load_existing=True, headless=False, max_additional_pages=None):
    """Voer de Werkspot scraper uit met gegeven parameters."""
    scraper = WerkspotScraper(headless=headless, load_existing=load_existing)
    
    try:
        # Scrape de pagina
        print("=" * 60)
        print("WERKSPOT SCRAPER")
        print("=" * 60)
        
        companies = scraper.scrape_category_page(target_url, max_additional_pages=max_additional_pages)
        
        print(f"\n✅ Scrapen voltooid!")
        print(f"📊 Totaal verzameld: {len(companies)} bedrijven")
        
        # Opslaan met aangepaste bestandsnamen indien opgegeven
        print("\n💾 Gegevens opslaan...")
        if csv_filename:
            scraper.save_to_csv(csv_filename)
        else:
            scraper.save_to_csv()
            
        if excel_filename:
            scraper.save_to_excel(excel_filename)
        else:
            scraper.save_to_excel()
        
        return companies
        
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

