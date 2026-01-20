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

class TrustooPreciseScraper:
    def __init__(self, headless=True, load_existing=True, stop_callback=None):
        """Initialiseer de scraper voor Trustoo's specifieke structuur."""
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
        
        # Blokkeer locatie-detectie om te voorkomen dat Trustoo automatisch naar een specifieke locatie navigeert
        options.add_argument('--disable-geolocation')
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 2,  # Blokkeer geolocatie
            "profile.default_content_setting_values.notifications": 2  # Blokkeer notificaties
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
        
        # OPTIMALISATIE: Houd sets bij als instance variabelen (veel sneller!)
        self.existing_urls = set()
        self.existing_keys = set()
        
        # Checkpoint voor hervatten
        self.checkpoint_clicks = 0
        
        # Stop callback functie
        self.stop_callback = stop_callback
        
        # Flag om bij te houden of we gestopt zijn
        self._was_stopped = False
        
        # Ad Hoc Data API client (optioneel)
        self.ad_hoc_api = None
        try:
            from ad_hoc_data import AdHocDataAPI
            api_key = os.environ.get('AD_HOC_DATA_API_KEY', '52239725-9f5a-4719-94ac-563f789e537b')
            if api_key:
                self.ad_hoc_api = AdHocDataAPI(api_key=api_key)
                print("✅ Ad Hoc Data API verbinding actief")
        except Exception as e:
            print(f"⚠️ Ad Hoc Data API niet beschikbaar: {str(e)}")
            print("   Bedrijven worden opgeslagen zonder verrijking.")
        
        # Laad bestaande data als die er is
        if load_existing:
            self.load_existing_data()
        else:
            # Bij nieuw bestand: reset alle duplicate tracking
            self.existing_urls = set()
            self.existing_keys = set()
            self.companies_data = []
            print("🆕 Nieuw bestand - geen duplicaatcontrole op basis van oude data")
        
        # Mask automation
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def load_existing_data(self, csv_file="trustoo_elektriciens.csv", excel_file="trustoo_elektriciens.xlsx"):
        """Laad bestaande data vanuit CSV of Excel om te hervatten."""
        try:
            # Probeer eerst CSV (meest betrouwbaar)
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
                        if naam or adres:  # Alleen toevoegen als er data is
                            self.existing_keys.add((naam, adres))
                    print(f"✅ {len(self.companies_data)} bestaande bedrijven geladen vanuit {csv_file}")
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
            with open("checkpoint.txt", "w") as f:
                f.write(str(clicks))
        except:
            pass
    
    def load_checkpoint(self):
        """Laad checkpoint (aantal klikken)."""
        try:
            if os.path.exists("checkpoint.txt"):
                with open("checkpoint.txt", "r") as f:
                    clicks = int(f.read().strip())
                    self.checkpoint_clicks = clicks
                    print(f"📌 Checkpoint geladen: was gebleven bij {clicks} klikken")
                    return clicks
        except:
            pass
        return 0
    
    def extract_company_info(self, company_element):
        """Haal gegevens uit een enkel bedrijfsblok - PRECIES voor Trustoo's HTML."""
        # 1. Bedrijfsnaam - probeer meerdere selectors
        name = "Niet gevonden"
        name_selectors = [
            "h3.proNameNew-module__5tvS2q__companyName",  # Originele selector
            "h3[class*='companyName']",  # Meer flexibele selector
            "h3[class*='proName']",  # Alternatief
            "h2, h3",  # Fallback naar elke h2/h3
            "a[href*='/profiel/']",  # Fallback naar link tekst
        ]
        
        for selector in name_selectors:
            try:
                name_element = company_element.find_element(By.CSS_SELECTOR, selector)
                name_text = name_element.text.strip()
                if name_text and name_text != "Niet gevonden":
                    name = name_text
                    break
            except NoSuchElementException:
                continue
        
        # 2. Adres - probeer meerdere selectors
        address = "Niet gevonden"
        address_selectors = [
            # Nieuwe structuur: adres zit in ellipsis div binnen placeWrapper
            (By.XPATH, ".//div[contains(@class, 'proBullets-module__JgvdTG__list')]//div[contains(@class, 'ellipsis-module__O8e_Ha__ellipsis')]"),
            # Alternatief: zoek naar div met place icon en dan de tekst ernaast
            (By.XPATH, ".//div[contains(@class, 'proBullets-module__JgvdTG__list')]//div[contains(@class, 'placeWrapper')]//div[contains(text(), ',')]"),
            # Origineel: zoek naar div met komma in tekst
            (By.XPATH, ".//div[contains(@class, 'proBullets-module__JgvdTG__list')]//div[contains(text(), ',')]"),
            # Meer flexibel
            (By.XPATH, ".//div[contains(@class, 'proBullets')]//div[contains(text(), ',')]"),
            # Fallback
            (By.XPATH, ".//*[contains(text(), ',') and string-length(text()) > 5]"),
        ]
        
        for selector_type, selector in address_selectors:
            try:
                address_element = company_element.find_element(selector_type, selector)
                address_text = address_element.text.strip()
                if address_text and ',' in address_text and len(address_text) > 5:
                    address = address_text
                    break
            except NoSuchElementException:
                continue
        
        # 3. Telefoonnummer - zoek in proBullets
        phone = "Niet vermeld"
        try:
            # Kijk voor een div met telefoonnummer (niet in een link)
            phone_elements = company_element.find_elements(
                By.XPATH, 
                ".//div[contains(@class, 'proBullets-module__JgvdTG__list')]//div[contains(@class, 'underline')]"
            )
            for element in phone_elements:
                text = element.text.strip()
                if any(char.isdigit() for char in text) and len(text.replace(' ', '')) >= 8:
                    phone = text
                    break
        except Exception:
            pass
        
        # 4. TrustScore - zoek het b element met de score
        trust_score = "N/A"
        try:
            score_element = company_element.find_element(By.CSS_SELECTOR, "div.score-module__7oD7Ya__stars b")
            trust_score = score_element.text.strip() if score_element else "N/A"
        except NoSuchElementException:
            pass
        
        # 5. Aantal reviews - uit het kleine element naast de sterren
        num_reviews = "0"
        try:
            reviews_element = company_element.find_element(
                By.CSS_SELECTOR, 
                "div.score-module__7oD7Ya__stars small span:not(.hidden)"
            )
            reviews_text = reviews_element.text.strip()
            # Extraheer getal tussen haakjes
            import re
            match = re.search(r'\((\d+)\)', reviews_text)
            if match:
                num_reviews = match.group(1)
        except (NoSuchElementException, AttributeError):
            pass
        
        # 6. Beschikbaarheid - uit profile labels
        availability = []
        try:
            avail_elements = company_element.find_elements(
                By.CSS_SELECTOR, 
                "div.profileLabels-module__6DVY6G__profileLabel span"
            )
            for elem in avail_elements:
                text = elem.text.strip()
                if text and text not in ["local_offer", "flash_on", "grade"]:
                    availability.append(text)
        except NoSuchElementException:
            pass
        
        # 7. Link naar bedrijfspagina (algemeen, niet alleen elektricien)
        profile_url = ""
        try:
            # Zoek naar link naar profiel (algemeen)
            link_element = company_element.find_element(By.CSS_SELECTOR, "a[href*='/profiel/'], a[href*='/bedrijf/']")
            profile_url = link_element.get_attribute('href')
        except NoSuchElementException:
            # Fallback: zoek naar elke link die naar een bedrijfspagina lijkt
            try:
                links = company_element.find_elements(By.CSS_SELECTOR, "a[href]")
                for link in links:
                    href = link.get_attribute('href')
                    if href and ('/profiel/' in href or '/bedrijf/' in href):
                        profile_url = href
                        break
            except:
                pass
        
        # 8. Jaren in bedrijf (indien aanwezig)
        years_in_business = ""
        try:
            years_element = company_element.find_element(
                By.XPATH, 
                ".//div[contains(@class, 'proBullets-module__JgvdTG__list')]//div[contains(text(), 'jaar in bedrijf')]"
            )
            years_in_business = years_element.text.strip()
        except NoSuchElementException:
            pass
        
        # 9. Laatste review datum
        last_review = ""
        try:
            review_element = company_element.find_element(
                By.CSS_SELECTOR, 
                "span.proBullets-module__JgvdTG__lastReviewDate"
            )
            last_review = review_element.text.strip()
        except NoSuchElementException:
            pass
        
        # 10. Korte beschrijving
        description = ""
        try:
            desc_element = company_element.find_element(
                By.CSS_SELECTOR, 
                "div[style*='-webkit-line-clamp:2'] p"
            )
            description = desc_element.text.strip()
        except NoSuchElementException:
            pass
        
        return {
            'Naam': name,
            'Adres': address,
            'Telefoon': phone,
            'TrustScore': trust_score,
            'AantalReviews': num_reviews,
            'Beschikbaarheid': ', '.join(availability) if availability else "Niet vermeld",
            'ProfielURL': profile_url,
            'JarenInBedrijf': years_in_business,
            'LaatsteReview': last_review,
            'Beschrijving': description[:200] + "..." if len(description) > 200 else description
        }
    
    def click_show_more(self, max_clicks=None):
        """Klik op 'Toon meer resultaten' - blijft doorgaan tot er geen knop meer is."""
        clicks = 0
        consecutive_failures = 0
        max_failures = 5  # Stop na 5 opeenvolgende fouten
        
        if max_clicks is None:
            max_clicks = 9999  # Onbeperkt (of tot er geen knop meer is)
        
        while clicks < max_clicks and consecutive_failures < max_failures:
            try:
                # Wacht even voordat we opnieuw zoeken
                time.sleep(random.uniform(1, 2))
                
                # Zoek de knop met verschillende strategieën
                show_more_button = None
                
                # Strategie 1: Zoek op tekst
                try:
                    buttons = self.driver.find_elements(
                        By.XPATH, 
                        "//button[contains(text(), 'Toon meer resultaten') or contains(text(), 'Meer resultaten') or contains(text(), 'Laad meer')]"
                    )
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            show_more_button = btn
                            break
                except:
                    pass
                
                # Strategie 2: Zoek op data-attribute of class
                if not show_more_button:
                    try:
                        buttons = self.driver.find_elements(
                            By.CSS_SELECTOR, 
                            "button[data-test-id*='load'], button[class*='load-more'], button[class*='show-more']"
                        )
                        for btn in buttons:
                            if btn.is_displayed() and btn.is_enabled():
                                show_more_button = btn
                                break
                    except:
                        pass
                
                # Als geen knop gevonden, stop
                if not show_more_button:
                    print(f"Geen 'Toon meer resultaten' knop meer gevonden na {clicks} klikken.")
                    break
                
                # Scroll naar de knop
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                        show_more_button
                    )
                    time.sleep(random.uniform(0.5, 1))
                except:
                    pass
                
                # Klik op de knop met JavaScript (meer betrouwbaar)
                try:
                    self.driver.execute_script("arguments[0].click();", show_more_button)
                except:
                    # Fallback naar normale click
                    show_more_button.click()
                
                clicks += 1
                consecutive_failures = 0  # Reset failure counter
                print(f"✅ Klik {clicks}: Meer resultaten geladen...")
                
                # Wacht tot nieuwe content laadt - belangrijk!
                time.sleep(random.uniform(4, 6))
                
                # Wacht tot de pagina klaar is met laden
                try:
                    self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                except:
                    pass
                
            except StaleElementReferenceException:
                consecutive_failures += 1
                print(f"⚠️  Stale element (poging {consecutive_failures}/{max_failures}), wachten en opnieuw proberen...")
                time.sleep(random.uniform(2, 3))
                continue
            except Exception as e:
                consecutive_failures += 1
                print(f"⚠️  Fout bij klikken (poging {consecutive_failures}/{max_failures}): {str(e)[:100]}")
                if consecutive_failures >= max_failures:
                    print("❌ Te veel fouten, stoppen met klikken.")
                    break
                time.sleep(random.uniform(2, 3))
                continue
        
        return clicks
    
    def _ensure_nederland_url(self, target_url):
        """Zorg ervoor dat de URL naar Nederland verwijst, niet naar een specifieke locatie."""
        # Check stop callback VOORDAT we beginnen
        if self.stop_callback and self.stop_callback():
            raise Exception("STOP_REQUESTED")
        
        current_url = self.driver.current_url
        
        # ALTIJD naar Nederland gaan als dat de bedoeling is
        if "/nederland/" in target_url.lower():
            # Check of de URL NIET naar Nederland gaat
            if "/nederland/" not in current_url.lower():
                # Extract het pad na trustoo.nl - kan zijn: rosmalen, noord-brabant/rosmalen, etc.
                # Gebruik de originele target_url
                detected_location = re.search(r'https://trustoo\.nl/(.+?)/(.+?)/', current_url)
                if detected_location:
                    loc_str = detected_location.group(1)
                    print(f"   ⚠️  URL aangepast naar '{loc_str}', FORCEREN naar Nederland...")
                else:
                    print(f"   ⚠️  URL niet correct, FORCEREN naar Nederland...")
                
                # Check stop callback
                if self.stop_callback and self.stop_callback():
                    raise Exception("STOP_REQUESTED")
                
                # Clear ALLES om locatie-detectie te voorkomen
                self.driver.delete_all_cookies()
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                
                # Check stop callback
                if self.stop_callback and self.stop_callback():
                    raise Exception("STOP_REQUESTED")
                
                # Gebruik JavaScript om direct naar de originele URL te navigeren
                self.driver.execute_script(f"window.location.href = '{target_url}';")
                # Check stop callback tijdens wachten (elke seconde)
                for _ in range(4):
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    time.sleep(1)
                
                # Als JavaScript niet werkt, gebruik normale navigatie
                if "/nederland/" not in self.driver.current_url.lower():
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    self.driver.get(target_url)
                    # Check stop callback tijdens wachten (elke seconde)
                    for _ in range(4):
                        if self.stop_callback and self.stop_callback():
                            raise Exception("STOP_REQUESTED")
                        time.sleep(1)
                
                # Check stop callback
                if self.stop_callback and self.stop_callback():
                    raise Exception("STOP_REQUESTED")
                
                self.accept_cookies()
                # Check stop callback tijdens wachten
                for _ in range(2):
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    time.sleep(1)
                
                # Verifieer dat we nu op Nederland zijn
                final_url = self.driver.current_url
                if "/nederland/" in final_url.lower():
                    print(f"   ✅ Succesvol geforceerd naar: {final_url}")
                    return True
                else:
                    print(f"   ❌ Waarschuwing: URL is nog steeds niet correct: {final_url}")
                    return False
        return False
    
    def scrape_category_page(self, url, max_additional_pages=None, save_interval=10, resume_from_checkpoint=True):
        """Scrape een Trustoo categoriepagina met tussentijds opslaan."""
        # Clear alles VOORDAT we navigeren
        try:
            self.driver.delete_all_cookies()
            self.driver.execute_script("window.localStorage.clear();")
            self.driver.execute_script("window.sessionStorage.clear();")
        except:
            pass
        
        # Navigeer direct naar Nederland
        self.driver.get(url)
        
        # Accepteer cookies
        self.accept_cookies()
        
        # Wacht tot pagina geladen is
        time.sleep(3)
        
        # FORCEER de URL meerdere keren indien nodig (alleen loggen bij problemen)
        max_correction_attempts = 10
        correction_attempt = 0
        
        if "/nederland/" in url.lower():
            while correction_attempt < max_correction_attempts:
                current_url = self.driver.current_url
                
                # Check of de URL NIET naar Nederland gaat
                if "/nederland/" not in current_url.lower():
                    # Extract categorie uit URL (algemeen, niet alleen elektricien)
                    detected_location = re.search(r'https://trustoo\.nl/(.+?)/(.+?)/', current_url)
                    if detected_location:
                        loc_str = detected_location.group(1)
                        print(f"⚠️  URL aangepast naar: '{loc_str}', corrigeren...")
                    
                    # Clear alles opnieuw
                    self.driver.delete_all_cookies()
                    self.driver.execute_script("window.localStorage.clear();")
                    self.driver.execute_script("window.sessionStorage.clear();")
                    
                    # Gebruik JavaScript om direct te navigeren naar de originele URL
                    self.driver.execute_script(f"window.location.href = '{url}';")
                    time.sleep(4)
                    
                    # Als JavaScript niet werkt, gebruik normale navigatie
                    if "/nederland/" not in self.driver.current_url.lower():
                        self.driver.get(url)
                        time.sleep(4)
                    
                    self.accept_cookies()
                    time.sleep(2)
                    correction_attempt += 1
                else:
                    break
            
            # Laatste controle (alleen loggen bij fout)
            final_url = self.driver.current_url
            if "/nederland/" not in final_url.lower():
                print(f"\n❌ FOUT: URL is nog steeds niet correct: {final_url}")
                raise Exception(f"Kon niet naar Nederland-pagina navigeren. Huidige URL: {final_url}")
        
        # Eerst de initiële bedrijven verzamelen
        initial_count = len(self.companies_data)
        self._collect_companies_from_page(silent=False)  # Toon eerste batch
        
        clicks = 0
        # Alleen checkpoint gebruiken als we bestaande data laden (resume_from_checkpoint EN er zijn bestaande bedrijven)
        if resume_from_checkpoint and len(self.companies_data) > 0:
            clicks = self.load_checkpoint()
            if clicks > 0:
                print(f"📌 Checkpoint geladen: was gebleven bij {clicks} klikken")
                print(f"⏩ Snel doorklikken naar checkpoint...")
                # Snel doorklikken zonder te verzamelen tot we bij het checkpoint zijn (stil)
                for i in range(clicks):
                    try:
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        buttons = self.driver.find_elements(
                            By.CSS_SELECTOR, 
                            "button.button-module__4-hbqa__btnReset.button-module__4-hbqa__text.button-module__4-hbqa__larger"
                        )
                        for btn in buttons:
                            if btn.is_displayed() and btn.is_enabled():
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(2)
                                break
                    except:
                        pass
                
                # BELANGRIJK: Verzamel ALLE bedrijven van de huidige pagina NA het doorklikken!
                print(f"🔍 Verzamelen bedrijven van checkpoint pagina...")
                time.sleep(3)  # Wacht even tot pagina volledig geladen is
                checkpoint_before = len(self.companies_data)
                self._collect_companies_from_page(silent=False)
                checkpoint_after = len(self.companies_data)
                checkpoint_added = checkpoint_after - checkpoint_before
                if checkpoint_added > 0:
                    print(f"✅ {checkpoint_added} bedrijven verzameld van checkpoint pagina (totaal: {checkpoint_after})")
                else:
                    print(f"⚠️ Geen nieuwe bedrijven gevonden op checkpoint pagina (totaal: {checkpoint_after})")
        elif resume_from_checkpoint:
            # Als resume_from_checkpoint True is maar er zijn geen bestaande bedrijven, reset checkpoint
            print("📌 Nieuw bestand - checkpoint wordt genegeerd")
            try:
                if os.path.exists("checkpoint.txt"):
                    os.remove("checkpoint.txt")
                    print("🗑️ Oud checkpoint bestand verwijderd")
            except:
                pass
        
        consecutive_failures = 0
        max_failures = 5
        
        while (max_additional_pages is None or clicks < max_additional_pages) and consecutive_failures < max_failures:
            # Check of stoppen is aangevraagd - ELKE ITERATIE!
            if self.stop_callback and self.stop_callback():
                print("\n🛑 STOP gedetecteerd in main loop!")
                raise Exception("STOP_REQUESTED")
            
            # Check ook de _was_stopped flag
            if self._was_stopped:
                print("\n🛑 STOP flag gedetecteerd!")
                raise Exception("STOP_REQUESTED")
            
            try:
                # Controleer eerst of URL nog steeds correct is
                self._ensure_nederland_url(url)
                
                # Scroll eerst naar beneden om te zorgen dat de knop zichtbaar is
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                # Check stop callback tijdens scroll wachten
                wait_time = random.uniform(2, 4)
                for _ in range(int(wait_time)):
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    time.sleep(1)
                time.sleep(wait_time - int(wait_time))
                
                # Zoek de knop met de specifieke class
                show_more_button = None
                try:
                    # Eerst proberen met de specifieke class selector
                    buttons = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        "button.button-module__4-hbqa__btnReset.button-module__4-hbqa__text.button-module__4-hbqa__larger"
                    )
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            show_more_button = btn
                            break
                except Exception as e:
                    print(f"   ⚠️  Fout bij zoeken knop (class selector): {str(e)[:50]}")
                
                # Fallback: zoek op tekst als class selector niet werkt
                if not show_more_button:
                    try:
                        buttons = self.driver.find_elements(
                            By.XPATH, 
                            "//button[contains(text(), 'Toon meer resultaten')]"
                        )
                        for btn in buttons:
                            if btn.is_displayed() and btn.is_enabled():
                                show_more_button = btn
                                break
                    except Exception as e:
                        print(f"   ⚠️  Fout bij zoeken knop (text selector): {str(e)[:50]}")
                
                if not show_more_button:
                    print(f"\n✅ Geen 'Toon meer resultaten' knop meer gevonden na {clicks} klikken.")
                    print(f"   📊 Totaal aantal bedrijven verzameld: {len(self.companies_data)}")
                    # Laatste keer verzamelen om zeker te zijn dat we alles hebben
                    print(f"   🔍 Laatste scan voor alle bedrijven...")
                    self._collect_companies_from_page(silent=True)
                    print(f"   📊 Eindtotaal: {len(self.companies_data)} bedrijven")
                    break
                
                # Scroll naar de knop en klik
                try:
                    # Check stop callback VOORDAT we klikken
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                        show_more_button
                    )
                    # Check stop callback tijdens wachten
                    wait_time = random.uniform(0.5, 1)
                    for _ in range(int(wait_time * 2)):  # Check elke 0.5 seconde
                        if self.stop_callback and self.stop_callback():
                            raise Exception("STOP_REQUESTED")
                        time.sleep(0.5)
                    time.sleep(wait_time - int(wait_time))
                    
                    # Check stop callback VOORDAT we klikken
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    
                    self.driver.execute_script("arguments[0].click();", show_more_button)
                except Exception as e:
                    try:
                        show_more_button.click()
                    except Exception as e2:
                        print(f"   ⚠️  Kon niet klikken: {str(e2)[:50]}")
                        consecutive_failures += 1
                        continue
                
                clicks += 1
                consecutive_failures = 0
                
                # Sla checkpoint op (stil)
                self.save_checkpoint(clicks)
                
                # Wacht LANGER tot content laadt (VOORZICHTIG - voorkom IP blok!)
                # Check stop callback tijdens wachten!
                wait_time = random.uniform(8, 12)
                print(f"⏳ Wachten {int(wait_time)} seconden tot nieuwe content laadt...")
                for _ in range(int(wait_time)):
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    time.sleep(1)
                time.sleep(wait_time - int(wait_time))  # Rest van de tijd
                
                try:
                    self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                except:
                    pass
                
                # Extra wachttijd voor dynamische content (VOORZICHTIG!)
                # Check stop callback tijdens wachten!
                extra_wait = random.uniform(3, 5)
                print(f"⏳ Extra wachttijd {int(extra_wait)} seconden voor dynamische content...")
                for _ in range(int(extra_wait)):
                    if self.stop_callback and self.stop_callback():
                        raise Exception("STOP_REQUESTED")
                    time.sleep(1)
                time.sleep(extra_wait - int(extra_wait))  # Rest van de tijd
                
                # Wacht tot nieuwe bedrijven zichtbaar zijn op de pagina
                print("🔍 Controleren of nieuwe bedrijven zijn geladen...")
                try:
                    # Scroll naar beneden om te zorgen dat nieuwe content zichtbaar is
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    # Scroll terug naar boven
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
                except:
                    pass
                
                # Controleer of URL nog steeds correct is (stil, alleen bij problemen)
                self._ensure_nederland_url(url)
                
                # Check opnieuw of stoppen is aangevraagd VOORDAT we verzamelen
                if self.stop_callback and self.stop_callback():
                    raise Exception("STOP_REQUESTED")
                
                # Verzamel nieuwe bedrijven
                new_count_before = len(self.companies_data)
                print(f"🔍 Verzamelen bedrijven van pagina... (huidig totaal: {new_count_before})")
                self._collect_companies_from_page(silent=True)
                new_count_after = len(self.companies_data)
                new_companies = new_count_after - new_count_before
                
                # Check opnieuw na verzamelen
                if self.stop_callback and self.stop_callback():
                    raise Exception("STOP_REQUESTED")
                
                # ALTIJD tonen hoeveel bedrijven zijn gevonden (ook als 0)
                if new_companies > 0:
                    print(f"✅ {new_companies} nieuwe bedrijven gevonden (totaal: {new_count_after})")
                else:
                    print(f"⚠️ Geen nieuwe bedrijven gevonden op deze pagina (totaal blijft: {new_count_after})")
                
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
                # Check of dit een stop request is
                if str(e) == "STOP_REQUESTED":
                    print(f"\n⚠️ Stop aangevraagd")
                    print(f"📊 Tot nu toe verzameld: {len(self.companies_data)} bedrijven")
                    print(f"💾 Bestanden worden opgeslagen...")
                    # Stop flag zetten zodat run_scraper weet dat we gestopt zijn
                    self._was_stopped = True
                    # VERZAMEL NOG EEN KEER ALLE BEDRIJVEN VAN DE HUIDIGE PAGINA VOORDAT WE STOPPEN
                    try:
                        if self.driver:
                            # Laatste keer verzamelen om zeker te zijn dat we alles hebben
                            print("🔍 Laatste scan voor alle bedrijven op huidige pagina...")
                            self._collect_companies_from_page(silent=True)
                            print(f"📊 Eindtotaal na laatste scan: {len(self.companies_data)} bedrijven")
                    except Exception as collect_err:
                        print(f"⚠️ Fout bij laatste verzamelen: {collect_err}")
                    # SLA EERST DATA OP VOORDAT BROWSER SLUIT
                    # Note: Bestanden worden opgeslagen door run_scraper_thread in app.py
                    # Hier slaan we alleen op als backup met standaard namen
                    try:
                        if len(self.companies_data) > 0:
                            # Maak scrapes directory aan als die niet bestaat
                            os.makedirs("scrapes", exist_ok=True)
                            # Tussentijds opslaan met standaard namen als backup
                            backup_csv = os.path.join("scrapes", f"backup_stopped_{int(time.time())}.csv")
                            backup_excel = os.path.join("scrapes", f"backup_stopped_{int(time.time())}.xlsx")
                            self.save_to_csv(backup_csv, silent=True)
                            self.save_to_excel(backup_excel, silent=True)
                            print(f"✅ {len(self.companies_data)} bedrijven opgeslagen als backup: {backup_csv}")
                    except Exception as save_err:
                        print(f"⚠️ Fout bij tussentijds opslaan: {save_err}")
                        import traceback
                        print(f"Traceback: {traceback.format_exc()}")
                    # SLUIT BROWSER DIRECT BIJ STOPPEN
                    try:
                        if self.driver:
                            self.driver.quit()
                            print("🔒 Browser gesloten")
                    except:
                        pass
                    # Break uit de loop
                    break
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
            
            # Vind ALLE bedrijfscontainers - probeer meerdere keren om te zorgen dat alle content geladen is
            company_containers = []
            
            # NIEUWE SELECTOR: Trustoo gebruikt nu div[id^="_pro_"][data-pro-id] voor elke bedrijfskaart
            # Dit is de meest betrouwbare selector omdat elk bedrijf een unieke ID heeft die begint met "_pro_"
            for attempt in range(3):
                containers = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "div[id^='_pro_'][data-pro-id]"
                )
                if len(containers) > len(company_containers):
                    company_containers = containers
                if attempt < 2:
                    time.sleep(0.5)
                    # Scroll een beetje om lazy loading te triggeren
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
                    time.sleep(0.5)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
            
            # Als eerste selector niets vindt, probeer alternatieve selectors (fallback voor oude structuur)
            if len(company_containers) == 0:
                alternative_selectors = [
                    "div.proListItemNewest-module__tr-fyq__mainSection",  # Nieuwe class-based selector
                    "div[data-test-id='pro-list-item']",  # Oude selector (voor backwards compatibility)
                    "div[class*='pro-list-item']",
                    "div[class*='company-card']",
                    "article[class*='company']",
                ]
                
                for selector in alternative_selectors:
                    try:
                        containers = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if len(containers) > len(company_containers):
                            company_containers = containers
                            if not silent:
                                print(f"   ✅ Alternatieve selector werkt: {selector} ({len(containers)} containers)")
                            break
                    except Exception as e:
                        continue
            
            if not silent:
                print(f"   📋 Gevonden {len(company_containers)} bedrijfscontainers op pagina")
            elif len(company_containers) > 0:
                print(f"   📋 Gevonden {len(company_containers)} bedrijfscontainers op pagina")
            
            # DEBUG: Als er geen containers zijn gevonden, log wat er wel op de pagina staat
            if len(company_containers) == 0:
                print(f"   ⚠️  GEEN bedrijfscontainers gevonden!")
                print(f"   🔍 Debug: Zoeken naar mogelijke containers...")
                try:
                    # Probeer verschillende algemene selectors om te zien wat er op de pagina staat
                    all_divs = self.driver.find_elements(By.CSS_SELECTOR, "div")
                    print(f"   📊 Totaal aantal divs op pagina: {len(all_divs)}")
                    
                    # Zoek naar divs met data-test-id attributen
                    test_id_divs = self.driver.find_elements(By.CSS_SELECTOR, "[data-test-id]")
                    if test_id_divs:
                        print(f"   📊 Divs met data-test-id: {len(test_id_divs)}")
                        # Toon eerste paar voorbeelden
                        for i, div in enumerate(test_id_divs[:5]):
                            test_id = div.get_attribute('data-test-id')
                            print(f"      - data-test-id='{test_id}'")
                    
                    # Zoek naar links naar profielen
                    profile_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/profiel/'], a[href*='/bedrijf/']")
                    if profile_links:
                        print(f"   📊 Links naar profielen gevonden: {len(profile_links)}")
                except Exception as debug_err:
                    print(f"   ⚠️  Debug fout: {str(debug_err)[:100]}")
            
            added_count = 0
            skipped_count = 0
            
            for container in company_containers:
                # Check of stoppen is aangevraagd tijdens verzamelen
                if self.stop_callback and self.stop_callback():
                    raise Exception("STOP_REQUESTED")
                try:
                    company_info = self.extract_company_info(container)
                    
                    # Check of het een nieuw bedrijf is - ALLE bedrijven toevoegen, alleen duplicaten overslaan
                    is_new = False
                    skip_reason = ""
                    
                    # BELANGRIJK: Skip bedrijven waarvan naam EN adres beide "Niet gevonden" zijn
                    # Dit zijn waarschijnlijk fouten in de scraping, geen echte bedrijven
                    naam = company_info.get('Naam', '') or ''
                    adres = company_info.get('Adres', '') or ''
                    
                    if naam == "Niet gevonden" and adres == "Niet gevonden":
                        skip_reason = "geen data gevonden"
                        skipped_count += 1
                        if not silent:
                            print(f"⚠️ Bedrijf overgeslagen: geen naam of adres gevonden")
                        continue
                    
                    # Gebruik URL als primaire identifier als die er is
                    if company_info.get('ProfielURL') and company_info['ProfielURL']:
                        if company_info['ProfielURL'] not in self.existing_urls:
                            is_new = True
                        else:
                            skip_reason = "duplicate URL"
                    else:
                        # Als er geen URL is, gebruik naam+adres als identifier
                        # Maar alleen als minstens één van beide gevonden is
                        if naam != "Niet gevonden" or adres != "Niet gevonden":
                            key = (naam, adres)
                            # Voeg toe als het niet een lege duplicate is
                            if key not in self.existing_keys:
                                is_new = True
                            else:
                                skip_reason = "duplicate naam+adres"
                        else:
                            skip_reason = "geen identifier beschikbaar"
                    
                    if is_new:
                        # Verrijk met Ad Hoc Data API direct na scrapen
                        if self.ad_hoc_api:
                            try:
                                company_info = self.ad_hoc_api.enrich_company(company_info)
                            except Exception as e:
                                if not silent:
                                    print(f"   ⚠️ Verrijking mislukt voor {company_info.get('Naam', 'Onbekend')}: {str(e)[:50]}")
                        
                        self.companies_data.append(company_info)
                        # Update de sets direct (veel sneller!)
                        if company_info.get('ProfielURL'):
                            self.existing_urls.add(company_info['ProfielURL'])
                        naam = company_info.get('Naam', '') or ''
                        adres = company_info.get('Adres', '') or ''
                        if naam or adres:  # Alleen toevoegen als er data is
                            self.existing_keys.add((naam, adres))
                        added_count += 1
                        
                        # Alleen tonen als niet silent
                        if not silent:
                            display_naam = company_info.get('Naam', 'Geen naam')[:50]
                            score = company_info.get('TrustScore', 'N/A')
                            reviews = company_info.get('AantalReviews', '0')
                            verrijkt = "✓" if company_info.get('AdHocData_Verrijkt') == 'Ja' else "○"
                            print(f"{verrijkt} {display_naam} (Score: {score}, Reviews: {reviews})")
                    else:
                        skipped_count += 1
                        if not silent and skip_reason:
                            print(f"⚠️ Overgeslagen: {skip_reason}")
                    
                except StaleElementReferenceException:
                    skipped_count += 1
                    continue
                except Exception as e:
                    # Check of dit een stop request is
                    if str(e) == "STOP_REQUESTED":
                        raise  # Her-raise zodat de outer loop het kan vangen
                    skipped_count += 1
                    if not silent:
                        print(f"⚠️ Fout bij extraheren: {str(e)[:50]}")
                    continue
            
            # ALTIJD totaal tonen (ook als silent, maar alleen als er iets is gebeurd)
            if not silent:
                if added_count > 0:
                    print(f"📊 Toegevoegd: {added_count}, Overgeslagen: {skipped_count}, Totaal: {len(self.companies_data)}")
                elif skipped_count > 0:
                    print(f"⚠️  Alle {skipped_count} bedrijven waren duplicates, Totaal: {len(self.companies_data)}")
            elif added_count > 0 or skipped_count > 0:
                # Zelfs in silent mode, log als er activiteit was
                print(f"   📊 Verzameld: {added_count} nieuw, {skipped_count} duplicates, Totaal: {len(self.companies_data)}")
                    
        except Exception as e:
            # Check of dit een stop request is - her-raise zodat outer loop het kan vangen
            if str(e) == "STOP_REQUESTED":
                raise
            print(f"   ⚠️  Fout bij verzamelen bedrijven: {str(e)[:80]}")
    
    def accept_cookies(self):
        """Accepteer cookie melding."""
        try:
            cookie_selectors = [
                "button:contains('Accepteren')",
                "button:contains('Akkoord')",
                "button:contains('Accepteer')",
                "[id*='cookie'] button",
                "[class*='cookie'] button"
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
            print(f"Geen cookie melding of fout: {e}")
    
    def save_to_excel(self, filename="trustoo_elektriciens.xlsx", silent=False):
        """Sla gegevens op in Excel."""
        if not self.companies_data:
            if not silent:
                print("Geen gegevens om op te slaan.")
            return
        
        df = pd.DataFrame(self.companies_data)
        
        # Maak kolommen leesbaarder - voeg Ad Hoc Data velden toe
        column_order = [
            'Naam', 'Adres', 'Telefoon', 'Email', 'Website', 'Contactpersoon',
            'TrustScore', 'AantalReviews', 'Beschikbaarheid', 'JarenInBedrijf', 
            'LaatsteReview', 'SBI_Code', 'Beschrijving', 'ProfielURL', 'AdHocData_Verrijkt'
        ]
        
        # Alleen kolommen die bestaan
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]
        
        df.to_excel(filename, index=False)
        if not silent:
            print(f"💾 {len(self.companies_data)} bedrijven opgeslagen in: {filename}")
        return filename
    
    def save_to_csv(self, filename="trustoo_elektriciens.csv", silent=False):
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
    
    def force_stop_and_save(self, csv_filename=None, excel_filename=None, title=None):
        """FORCEER stop en sla bestanden direct op."""
        print("\n🛑 FORCE STOP - Browser wordt gesloten en bestanden worden opgeslagen...")
        
        self._was_stopped = True
        
        # Sla bestanden op VOORDAT we de browser sluiten
        if len(self.companies_data) > 0:
            try:
                # Genereer bestandsnamen
                output_dir = "scrapes"
                if title:
                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                    safe_title = safe_title.replace(' ', '_')
                    output_dir = os.path.join("scrapes", safe_title)
                os.makedirs(output_dir, exist_ok=True)
                
                base_name = title.replace(' ', '_').lower() if title else "trustoo_scrape"
                base_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-'))
                
                if not csv_filename:
                    csv_filename = os.path.join(output_dir, f"{base_name}.csv")
                else:
                    csv_filename = os.path.join(output_dir, os.path.basename(csv_filename))
                    
                if not excel_filename:
                    excel_filename = os.path.join(output_dir, f"{base_name}.xlsx")
                else:
                    excel_filename = os.path.join(output_dir, os.path.basename(excel_filename))
                
                # Sla op
                self.save_to_csv(csv_filename, silent=True)
                self.save_to_excel(excel_filename, silent=True)
                print(f"✅ {len(self.companies_data)} bedrijven opgeslagen!")
                print(f"📁 CSV: {csv_filename}")
                print(f"📁 Excel: {excel_filename}")
                
                return csv_filename, excel_filename
            except Exception as e:
                print(f"⚠️ Fout bij opslaan: {e}")
                # Probeer met standaard namen
                try:
                    self.save_to_csv()
                    self.save_to_excel()
                except:
                    pass
        
        # SLUIT BROWSER DIRECT
        try:
            if self.driver:
                self.driver.quit()
                print("🔒 Browser geforceerd gesloten")
        except:
            pass
        
        return None, None
    
    def close(self):
        """Sluit de browser en Ad Hoc Data API session."""
        # Sluit Ad Hoc Data API session
        if self.ad_hoc_api:
            try:
                self.ad_hoc_api.close()
            except:
                pass
        
        # Sluit browser
        if self.driver:
            try:
                self.driver.quit()
                print("Browser gesloten.")
            except:
                pass

def run_scraper(target_url, csv_filename=None, excel_filename=None, load_existing=True, headless=False, max_additional_pages=None, title=None, stop_callback=None):
    """Voer de scraper uit met gegeven parameters."""
    scraper = TrustooPreciseScraper(headless=headless, load_existing=load_existing, stop_callback=stop_callback)
    
    try:
        # Scrape de pagina
        # resume_from_checkpoint moet alleen True zijn als load_existing True is
        resume_from_checkpoint = load_existing
        companies = scraper.scrape_category_page(target_url, max_additional_pages=max_additional_pages, resume_from_checkpoint=resume_from_checkpoint)
        
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
        base_name = title.replace(' ', '_').lower() if title else "trustoo_scrape"
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
        # ALTIJD opslaan, ook als gestopt
        print("💾 Bestanden opslaan...")
        try:
            scraper.save_to_csv(csv_filename, silent=True)
            scraper.save_to_excel(excel_filename, silent=True)
            print(f"✅ {len(companies)} bedrijven opgeslagen")
        except Exception as save_error:
            print(f"⚠️ Fout bij opslaan: {save_error}")
            # Probeer nog een keer met standaard namen
            try:
                scraper.save_to_csv()
                scraper.save_to_excel()
            except:
                pass
        
        return companies, csv_filename, excel_filename
        
    except Exception as e:
        # Check of dit een stop request is
        is_stop_request = "STOP_REQUESTED" in str(e) or scraper._was_stopped
        
        if is_stop_request:
            print(f"\n⚠️ Scrapen gestopt door gebruiker")
            print(f"📊 Tot nu toe verzameld: {len(scraper.companies_data)} bedrijven")
        else:
            print(f"\n❌ Fout opgetreden: {e}")
        
        # Probeer nog steeds op te slaan wat we hebben
        try:
            if len(scraper.companies_data) > 0:
                print("\n💾 Proberen bestanden op te slaan met verzamelde data...")
                
                # Genereer bestandsnamen als die er nog niet zijn
                if not csv_filename or not excel_filename:
                    output_dir = "scrapes"
                    if title:
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_title = safe_title.replace(' ', '_')
                        output_dir = os.path.join("scrapes", safe_title)
                    os.makedirs(output_dir, exist_ok=True)
                    
                    base_name = title.replace(' ', '_').lower() if title else "trustoo_scrape"
                    base_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-'))
                    
                    if not csv_filename:
                        csv_filename = os.path.join(output_dir, f"{base_name}.csv")
                    if not excel_filename:
                        excel_filename = os.path.join(output_dir, f"{base_name}.xlsx")
                
                scraper.save_to_csv(csv_filename)
                scraper.save_to_excel(excel_filename)
                print(f"✅ Bestanden opgeslagen: {csv_filename}")
                
                # Als gestopt, return de data en bestanden
                if is_stop_request:
                    return scraper.companies_data, csv_filename, excel_filename
        except Exception as save_err:
            print(f"⚠️ Fout bij opslaan: {save_err}")
        
        # Alleen re-raise als het geen stop request was
        if not is_stop_request:
            raise
    finally:
        scraper.close()

# 💡 HOOFDGEBRUIK - Aangepast voor jouw Trustoo URL
if __name__ == "__main__":
    import sys
    
    # Als er command line argumenten zijn, gebruik die
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        csv_file = sys.argv[2] if len(sys.argv) > 2 else None
        excel_file = sys.argv[3] if len(sys.argv) > 3 else None
        load_existing = sys.argv[4].lower() == 'true' if len(sys.argv) > 4 else True
        
        run_scraper(target_url, csv_file, excel_file, load_existing)
    else:
        # Standaard gedrag (voor backwards compatibility)
        scraper = TrustooPreciseScraper(headless=False)
        
        try:
            target_url = "https://trustoo.nl/nederland/elektricien/"
            
            print("=" * 60)
            print("TRUSTOO SCRAPER - ELEKTRICIENS")
            print("=" * 60)
            
            companies = scraper.scrape_category_page(target_url, max_additional_pages=None)
            
            print(f"\n✅ Scrapen voltooid!")
            print(f"📊 Totaal verzameld: {len(companies)} bedrijven")
            
            # Toon een voorbeeld
            if companies:
                print("\n📋 Voorbeeld van eerste resultaat:")
                example = companies[0]
                for key, value in example.items():
                    if value:
                        print(f"  {key}: {value}")
            
            # Opslaan
            print("\n💾 Gegevens opslaan...")
            scraper.save_to_excel()
            scraper.save_to_csv()
            
        except Exception as e:
            print(f"\n❌ Fout opgetreden: {e}")
        finally:
            scraper.close()