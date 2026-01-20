"""
Ad Hoc Data API integratie module.
Verrijkt bedrijfsgegevens met data van Ad Hoc Data API.
"""

import os
import requests
import time
from typing import Dict, List, Optional


class AdHocDataAPI:
    """Client voor Ad Hoc Data API."""
    
    BASE_URL = "https://api.adhocdata.nl"
    API_VERSION = "1.0"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialiseer Ad Hoc Data API client.
        
        Args:
            api_key: API key voor authenticatie. Als None, wordt AD_HOC_DATA_API_KEY uit environment gehaald.
        """
        self.api_key = api_key or os.getenv('AD_HOC_DATA_API_KEY')
        if not self.api_key:
            raise ValueError("AD_HOC_DATA_API_KEY niet gevonden. Zet deze in environment variables of geef door als parameter.")
        
        self.session = requests.Session()
        # Ad Hoc Data API gebruikt mogelijk een andere authenticatie methode
        # Probeer beide: Bearer token en API key als header
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'X-API-Key': self.api_key,  # Alternatieve methode
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def lookup(self, company_name: str, company_address: str = None, lookup_type: str = "bedrijf") -> Optional[Dict]:
        """
        Voer een lookup uit op de Ad Hoc Data API met zowel naam als adres.
        
        Args:
            company_name: Bedrijfsnaam
            company_address: Bedrijfsadres (optioneel, maar aanbevolen voor betere match)
            lookup_type: Type lookup (standaard: "bedrijf")
        
        Returns:
            Dict met resultaten of None bij fout
        """
        try:
            # Gebruik de juiste base URL: api.adhocdata.nl
            # Probeer verschillende mogelijke lookup endpoints
            endpoints_to_try = [
                f"{self.BASE_URL}/nl-basis/{self.API_VERSION}/lookup",
                f"{self.BASE_URL}/nl-basis/{self.API_VERSION}/search",
                f"{self.BASE_URL}/nl-basis/{self.API_VERSION}/companies",
                f"{self.BASE_URL}/nl-basis/{self.API_VERSION}/bedrijven",
            ]
            
            # Stuur zowel naam als adres mee voor betere matching
            params = {
                'q': company_name,
            }
            
            # Voeg adres toe als parameter als het beschikbaar is
            if company_address and company_address != "Niet gevonden":
                params['address'] = company_address
                params['adres'] = company_address  # Probeer ook Nederlandse naam
            
            # Probeer elk endpoint
            for url in endpoints_to_try:
                try:
                    response = self.session.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 404:
                        continue  # Probeer volgende endpoint
                    else:
                        # Andere fout (401, 403, etc.)
                        response.raise_for_status()
                        
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404:
                        continue  # Probeer volgende endpoint
                    else:
                        raise  # Her-raise andere HTTP errors
                except:
                    continue  # Probeer volgende endpoint
            
            # Geen endpoint werkte
            print(f"⚠️ Ad Hoc Data API: geen werkend endpoint gevonden voor lookup")
            print(f"   Probeerde: {', '.join(endpoints_to_try)}")
            print(f"   Parameters: q={company_name[:30]}..., address={company_address[:30] if company_address else 'None'}...")
            return None
            
        except requests.exceptions.RequestException as e:
            # Alleen loggen als het niet een 404 is (die hebben we al afgehandeld)
            if "404" not in str(e):
                print(f"⚠️ Fout bij Ad Hoc Data API lookup voor '{company_name}': {str(e)}")
            return None
        except Exception as e:
            print(f"⚠️ Onverwachte fout bij Ad Hoc Data API lookup: {str(e)}")
            return None
    
    def enrich_company(self, company_data: Dict) -> Dict:
        """
        Verrijk bedrijfsgegevens met data van Ad Hoc Data API.
        Gebruikt zowel bedrijfsnaam als adres voor betere matching.
        
        Args:
            company_data: Dict met bedrijfsgegevens (moet minimaal 'Naam' en 'Adres' bevatten)
        
        Returns:
            Verrijkt dict met extra velden van Ad Hoc Data
        """
        enriched = company_data.copy()
        
        # Haal zowel naam als adres op voor matching
        company_name = company_data.get('Naam', '')
        company_address = company_data.get('Adres', '')
        
        # Beide moeten beschikbaar zijn voor een goede match
        if not company_name or company_name == "Niet gevonden":
            enriched['AdHocData_Verrijkt'] = 'Nee (geen naam)'
            return enriched
        
        if not company_address or company_address == "Niet gevonden":
            enriched['AdHocData_Verrijkt'] = 'Nee (geen adres)'
            return enriched
        
        # Voer lookup uit met zowel naam als adres
        result = self.lookup(company_name, company_address)
        
        if result:
            # Voeg relevante velden toe aan enriched data
            # Pas dit aan op basis van wat de API daadwerkelijk teruggeeft
            api_data = result
            if isinstance(result, dict):
                # Als result een dict is, probeer verschillende mogelijke structuren
                if 'data' in result:
                    api_data = result['data']
                elif 'result' in result:
                    api_data = result['result']
                elif 'results' in result and len(result['results']) > 0:
                    # Als er meerdere resultaten zijn, zoek de beste match op basis van naam EN adres
                    results = result['results']
                    best_match = None
                    matched = False
                    
                    for res in results:
                        # Check of naam en adres matchen
                        res_name = res.get('naam', '') or res.get('Naam', '') or res.get('name', '')
                        res_address = res.get('adres', '') or res.get('Adres', '') or res.get('address', '')
                        
                        # Check of naam matcht (case-insensitive, gedeeltelijke match)
                        name_match = res_name.lower() in company_name.lower() or company_name.lower() in res_name.lower()
                        
                        # Check of adres matcht (check op postcode of stad)
                        address_match = False
                        if res_address and company_address:
                            # Vergelijk postcodes of steden
                            res_parts = res_address.lower().split(',')
                            company_parts = company_address.lower().split(',')
                            # Check of er overlap is in adres delen
                            address_match = any(part.strip() in company_address.lower() or part.strip() in res_address.lower() 
                                              for part in res_parts if len(part.strip()) > 3)
                        
                        if name_match and address_match:
                            best_match = res
                            matched = True
                            break
                    
                    # Alleen gebruiken als beide naam EN adres matchen
                    if matched and best_match:
                        api_data = best_match
                    else:
                        # Geen goede match gevonden
                        enriched['AdHocData_Verrijkt'] = 'Nee (geen match op naam+adres)'
                        return enriched
                else:
                    # Single result - check ook hier of naam en adres matchen
                    res_name = api_data.get('naam', '') or api_data.get('Naam', '') or api_data.get('name', '')
                    res_address = api_data.get('adres', '') or api_data.get('Adres', '') or api_data.get('address', '')
                    
                    name_match = res_name.lower() in company_name.lower() or company_name.lower() in res_name.lower()
                    address_match = False
                    if res_address and company_address:
                        res_parts = res_address.lower().split(',')
                        address_match = any(part.strip() in company_address.lower() or part.strip() in res_address.lower() 
                                          for part in res_parts if len(part.strip()) > 3)
                    
                    if not (name_match and address_match):
                        # Geen match
                        enriched['AdHocData_Verrijkt'] = 'Nee (geen match op naam+adres)'
                        return enriched
                
                # Alleen hier komen als er een match is - haal de gevraagde velden op
                # Website
                website = api_data.get('website', '') or api_data.get('Website', '') or api_data.get('url', '')
                if website and website != enriched.get('Website', ''):
                    enriched['Website'] = website
                
                # Telefoonnummer (overschrijf alleen als Ad Hoc Data een betere heeft)
                phone = api_data.get('telefoon', '') or api_data.get('Telefoon', '') or api_data.get('phone', '')
                if phone and (not enriched.get('Telefoon') or enriched.get('Telefoon') == "Niet vermeld"):
                    enriched['Telefoon'] = phone
                
                # Emailadres
                email = api_data.get('email', '') or api_data.get('Email', '') or api_data.get('e_mail', '')
                enriched['Email'] = email if email else ''
                
                # Contactpersoon
                contact = api_data.get('contactpersoon', '') or api_data.get('Contactpersoon', '') or api_data.get('contact', '')
                enriched['Contactpersoon'] = contact if contact else ''
                
                # SBI code
                sbi = api_data.get('sbi', '') or api_data.get('SBI', '') or api_data.get('sbi_code', '')
                enriched['SBI_Code'] = sbi if sbi else ''
                
                enriched['AdHocData_Verrijkt'] = 'Ja'
        else:
            enriched['AdHocData_Verrijkt'] = 'Nee'
            # Zet lege waarden voor velden die niet gevonden zijn
            enriched['Email'] = enriched.get('Email', '')
            enriched['Contactpersoon'] = enriched.get('Contactpersoon', '')
            enriched['SBI_Code'] = enriched.get('SBI_Code', '')
        
        # Rate limiting - wacht even tussen requests
        time.sleep(0.3)
        
        return enriched
    
    def enrich_companies_batch(self, companies: List[Dict], delay: float = 0.5) -> List[Dict]:
        """
        Verrijk een lijst van bedrijven met Ad Hoc Data.
        
        Args:
            companies: Lijst van bedrijfsdicts
            delay: Wachtijd tussen requests in seconden (voor rate limiting)
        
        Returns:
            Lijst van verrijkte bedrijfsdicts
        """
        enriched_companies = []
        
        print(f"\n🔄 Verrijken van {len(companies)} bedrijven met Ad Hoc Data...")
        
        for i, company in enumerate(companies, 1):
            enriched = self.enrich_company(company)
            enriched_companies.append(enriched)
            
            if i % 10 == 0:
                print(f"   Verrijkt {i}/{len(companies)} bedrijven...")
            
            # Rate limiting
            if i < len(companies):
                time.sleep(delay)
        
        print(f"✅ {len(enriched_companies)} bedrijven verrijkt met Ad Hoc Data")
        
        return enriched_companies
    
    def close(self):
        """Sluit de session."""
        self.session.close()


def enrich_with_ad_hoc_data(companies: List[Dict], api_key: Optional[str] = None) -> List[Dict]:
    """
    Helper functie om bedrijven te verrijken met Ad Hoc Data.
    
    Args:
        companies: Lijst van bedrijfsdicts
        api_key: Optionele API key (anders uit environment)
    
    Returns:
        Lijst van verrijkte bedrijfsdicts
    """
    try:
        api = AdHocDataAPI(api_key=api_key)
        enriched = api.enrich_companies_batch(companies)
        api.close()
        return enriched
    except Exception as e:
        print(f"⚠️ Kon Ad Hoc Data API niet gebruiken: {str(e)}")
        print("   Bedrijven worden opgeslagen zonder verrijking.")
        return companies

