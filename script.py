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
    def __init__(self, headless=True, load_existing=True):
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
        
        # Laad bestaande data als die er is
        if load_existing:
            self.load_existing_data()
        
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
        try:
            # 1. Bedrijfsnaam - uit h3 met specifieke class
            name_element = company_element.find_element(By.CSS_SELECTOR, "h3.proNameNew-module__5tvS2q__companyName")
            name = name_element.text.strip() if name_element else "Niet gevonden"
        except NoSuchElementException:
            name = "Niet gevonden"
        
        try:
            # 2. Adres - uit het eerste place item
            address_element = company_element.find_element(
                By.XPATH, 
                ".//div[contains(@class, 'proBullets-module__JgvdTG__list')]//div[contains(text(), ',')]"
            )
            address = address_element.text.strip() if address_element else "Niet gevonden"
        except NoSuchElementException:
            address = "Niet gevonden"
        
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
        
        # 7. Link naar bedrijfspagina
        profile_url = ""
        try:
            link_element = company_element.find_element(By.CSS_SELECTOR, "a[href*='/elektricien/']")
            profile_url = link_element.get_attribute('href')
        except NoSuchElementException:
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
        current_url = self.driver.current_url
        
        # ALTIJD naar Nederland gaan als dat de bedoeling is
        if "/nederland/" in target_url.lower():
            # Check of de URL NIET naar Nederland gaat
            if "/nederland/" not in current_url.lower():
                # Extract het pad na trustoo.nl - kan zijn: rosmalen, noord-brabant/rosmalen, etc.
                # We willen ALTIJD: trustoo.nl/nederland/elektricien/
                nederland_url = "https://trustoo.nl/nederland/elektricien/"
                
                detected_location = re.search(r'https://trustoo\.nl/(.+?)/elektricien', current_url)
                if detected_location:
                    loc_str = detected_location.group(1)
                    print(f"   ⚠️  URL aangepast naar '{loc_str}', FORCEREN naar Nederland...")
                else:
                    print(f"   ⚠️  URL niet correct, FORCEREN naar Nederland...")
                
                # Clear ALLES om locatie-detectie te voorkomen
                self.driver.delete_all_cookies()
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                
                # Gebruik JavaScript om direct naar Nederland te navigeren
                self.driver.execute_script(f"window.location.href = '{nederland_url}';")
                time.sleep(4)
                
                # Als JavaScript niet werkt, gebruik normale navigatie
                if "/nederland/" not in self.driver.current_url.lower():
                    self.driver.get(nederland_url)
                    time.sleep(4)
                
                self.accept_cookies()
                time.sleep(2)
                
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
        # FORCEER ALTIJD naar Nederland als dat de bedoeling is
        if "/nederland/" in url.lower():
            url = "https://trustoo.nl/nederland/elektricien/"
            print(f"🚀 FORCEREN naar Nederland-pagina: {url}")
        else:
            print(f"🚀 Scrapen gestart: {url}")
        
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
        
        # FORCEER de URL meerdere keren indien nodig
        max_correction_attempts = 10
        correction_attempt = 0
        
        if "/nederland/" in url.lower():
            while correction_attempt < max_correction_attempts:
                current_url = self.driver.current_url
                print(f"📍 Huidige URL (controle {correction_attempt + 1}): {current_url}")
                
                # Check of de URL NIET naar Nederland gaat
                if "/nederland/" not in current_url.lower():
                    detected_location = re.search(r'https://trustoo\.nl/(.+?)/elektricien', current_url)
                    if detected_location:
                        loc_str = detected_location.group(1)
                        print(f"⚠️  Trustoo heeft URL aangepast naar: '{loc_str}'")
                    else:
                        print(f"⚠️  URL is niet correct")
                    
                    print(f"🔄 FORCEREN naar Nederland (poging {correction_attempt + 1}/{max_correction_attempts})...")
                    
                    # Clear alles opnieuw
                    self.driver.delete_all_cookies()
                    self.driver.execute_script("window.localStorage.clear();")
                    self.driver.execute_script("window.sessionStorage.clear();")
                    
                    # Gebruik JavaScript om direct te navigeren
                    nederland_url = "https://trustoo.nl/nederland/elektricien/"
                    self.driver.execute_script(f"window.location.href = '{nederland_url}';")
                    time.sleep(4)
                    
                    # Als JavaScript niet werkt, gebruik normale navigatie
                    if "/nederland/" not in self.driver.current_url.lower():
                        self.driver.get(nederland_url)
                        time.sleep(4)
                    
                    self.accept_cookies()
                    time.sleep(2)
                    correction_attempt += 1
                else:
                    # URL bevat al "nederland", we zijn klaar
                    print(f"✅ URL is correct: {current_url}")
                    break
            
            # Laatste controle
            final_url = self.driver.current_url
            if "/nederland/" not in final_url.lower():
                print(f"\n❌ FOUT: URL is nog steeds niet correct: {final_url}")
                print(f"   Het script stopt omdat we niet op de Nederland-pagina zijn!")
                raise Exception(f"Kon niet naar Nederland-pagina navigeren. Huidige URL: {final_url}")
            else:
                print(f"✅ Finale URL bevestigd: {final_url}")
                print(f"✅ We scrapen nu ALLE elektriciens in NEDERLAND, niet alleen een specifieke locatie!")
        
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
        
        # Klik op 'Toon meer resultaten' - blijft doorgaan tot er geen knop meer is
        print(f"\n🔄 Stap 2: Meer resultaten laden (dit kan even duren)...")
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
                # Snel doorklikken zonder te verzamelen tot we bij het checkpoint zijn
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
                print(f"✅ Bij checkpoint aangekomen, nu verder scrapen vanaf hier...")
                print(f"   (Nieuwe bedrijven worden toegevoegd, bestaande worden automatisch overgeslagen)\n")
        
        consecutive_failures = 0
        max_failures = 5
        
        while (max_additional_pages is None or clicks < max_additional_pages) and consecutive_failures < max_failures:
            try:
                # Controleer eerst of URL nog steeds correct is
                self._ensure_nederland_url(url)
                
                # Scroll eerst naar beneden om te zorgen dat de knop zichtbaar is
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1, 2))
                
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
                    self._collect_companies_from_page()
                    print(f"   📊 Eindtotaal: {len(self.companies_data)} bedrijven")
                    break
                
                # Scroll naar de knop en klik
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
                        print(f"   ⚠️  Kon niet klikken: {str(e2)[:50]}")
                        consecutive_failures += 1
                        continue
                
                clicks += 1
                consecutive_failures = 0
                print(f"\n   ✅ Klik {clicks}: Meer resultaten geladen...")
                
                # Sla checkpoint op
                self.save_checkpoint(clicks)
                
                # Wacht langer tot content laadt (Trustoo heeft tijd nodig)
                time.sleep(random.uniform(5, 7))
                try:
                    self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                except:
                    pass
                
                # Extra wachttijd voor dynamische content
                time.sleep(random.uniform(2, 3))
                
                # Controleer of URL nog steeds correct is (Trustoo kan deze opnieuw aanpassen)
                self._ensure_nederland_url(url)
                
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
            # Vind ALLE bedrijfscontainers
            company_containers = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div[data-test-id='pro-list-item']"
            )
            
            print(f"   🔍 Gevonden containers op pagina: {len(company_containers)}")
            
            # OPTIMALISATIE: Gebruik de instance variabelen in plaats van elke keer opnieuw te maken!
            # Dit is VEEL sneller omdat we niet door alle 971 bedrijven hoeven te lopen
            
            added_count = 0
            skipped_count = 0
            
            for container in company_containers:
                try:
                    company_info = self.extract_company_info(container)
                    
                    # Check of het een nieuw bedrijf is - ALLE bedrijven toevoegen, alleen duplicaten overslaan
                    is_new = False
                    skip_reason = ""
                    
                    # Gebruik URL als primaire identifier als die er is
                    if company_info.get('ProfielURL') and company_info['ProfielURL']:
                        if company_info['ProfielURL'] not in self.existing_urls:
                            is_new = True
                        else:
                            skip_reason = "duplicate URL"
                    else:
                        # Als er geen URL is, gebruik naam+adres als identifier (ook als naam leeg is)
                        naam = company_info.get('Naam', '') or ''
                        adres = company_info.get('Adres', '') or ''
                        key = (naam, adres)
                        
                        # Voeg toe als het niet een lege duplicate is
                        if key not in self.existing_keys:
                            is_new = True
                        else:
                            skip_reason = "duplicate naam+adres"
                    
                    if is_new:
                        self.companies_data.append(company_info)
                        # Update de sets direct (veel sneller!)
                        if company_info.get('ProfielURL'):
                            self.existing_urls.add(company_info['ProfielURL'])
                        naam = company_info.get('Naam', '') or ''
                        adres = company_info.get('Adres', '') or ''
                        if naam or adres:  # Alleen toevoegen als er data is
                            self.existing_keys.add((naam, adres))
                        added_count += 1
                        
                        # Toon elk gevonden bedrijf
                        display_naam = company_info.get('Naam', 'Geen naam')[:50]
                        score = company_info.get('TrustScore', 'N/A')
                        reviews = company_info.get('AantalReviews', '0')
                        print(f"   ✓ {display_naam} (Score: {score}, Reviews: {reviews})")
                    else:
                        skipped_count += 1
                        # Geen berichten voor overgeslagen items
                    
                except StaleElementReferenceException:
                    skipped_count += 1
                    # Geen bericht voor stale element
                    continue
                except Exception as e:
                    skipped_count += 1
                    print(f"   ⚠️  Fout bij extraheren: {str(e)[:50]}")
                    continue
            
            # Toon alleen toegevoegde en totaal, geen overgeslagen berichten
            print(f"   📊 Toegevoegd: {added_count}, Totaal: {len(self.companies_data)}")
                    
        except Exception as e:
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
        
        # Maak kolommen leesbaarder
        column_order = [
            'Naam', 'Adres', 'Telefoon', 'TrustScore', 'AantalReviews',
            'Beschikbaarheid', 'JarenInBedrijf', 'LaatsteReview',
            'Beschrijving', 'ProfielURL'
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
    
    def close(self):
        """Sluit de browser."""
        if self.driver:
            self.driver.quit()
            print("Browser gesloten.")

def run_scraper(target_url, csv_filename=None, excel_filename=None, load_existing=True, headless=False, max_additional_pages=None):
    """Voer de scraper uit met gegeven parameters."""
    scraper = TrustooPreciseScraper(headless=headless, load_existing=load_existing)
    
    try:
        # Scrape de pagina
        print("=" * 60)
        print("TRUSTOO SCRAPER")
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