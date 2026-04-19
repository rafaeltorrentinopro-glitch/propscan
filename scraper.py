import requests
import json
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup

SUPA_URL = "https://luzxxlucfvsqmfhnlgmw.supabase.co"
SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx1enh4bHVjZnZzcW1maG5sZ213Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYzNzI5NDcsImV4cCI6MjA5MTk0ODk0N30.AFPwHfVEzh9Z4sPwulbeYphi0R60aKEd0lBKzskmyl8"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'fr-FR,fr;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# Tous les départements français
DEPARTEMENTS = [
    "01","02","03","04","05","06","07","08","09","10",
    "11","12","13","14","15","16","17","18","19","21",
    "22","23","24","25","26","27","28","29","30","31",
    "32","33","34","35","36","37","38","39","40","41",
    "42","43","44","45","46","47","48","49","50","51",
    "52","53","54","55","56","57","58","59","60","61",
    "62","63","64","65","66","67","68","69","70","71",
    "72","73","74","75","76","77","78","79","80","81",
    "82","83","84","85","86","87","88","89","90","91",
    "92","93","94","95","971","972","973","974"
]

def supabase_insert(annonce):
    try:
        r = requests.post(
            f"{SUPA_URL}/rest/v1/annonces",
            headers={
                'apikey': SUPA_KEY,
                'Authorization': f'Bearer {SUPA_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'resolution=ignore-duplicates'
            },
            json=annonce,
            timeout=10
        )
        return r.status_code in [200, 201, 409]
    except:
        return False

def calc_renta(prix, surface):
    loyer = surface * 15.5
    return round((loyer * 12) / prix * 100, 1) if prix > 0 else 0

def calc_cashflow(prix, surface):
    loyer = surface * 15.5
    emprunt = prix * 1.08 * 0.9
    tm = 0.032 / 12
    n = 240
    men = emprunt * (tm * (1+tm)**n) / ((1+tm)**n - 1)
    return round(loyer - men - (prix * 0.01 / 12))

def calc_score(renta, cashflow):
    s = 5.0
    if renta >= 10: s += 3
    elif renta >= 8: s += 2
    elif renta >= 6: s += 1
    if cashflow > 400: s += 1
    elif cashflow > 100: s += 0.5
    return min(round(s, 1), 10.0)

# ══ LEBONCOIN — toute la France par département ══
def scrape_leboncoin():
    print("→ LeBonCoin (toute la France)...")
    annonces = []
    
    for dep in DEPARTEMENTS:
        try:
            payload = {
                "limit": 100,
                "limit_alu": 3,
                "filters": {
                    "category": {"id": "9"},
                    "enums": {
                        "ad_type": ["offer"],
                        "real_estate_type": ["1","2","3","4","5"]
                    },
                    "location": {
                        "locations": [{"locationType": "department", "department_id": dep}]
                    },
                    "ranges": {
                        "price": {"min": 20000, "max": 2000000},
                        "square": {"min": 10}
                    }
                },
                "sort_by": "time",
                "sort_order": "desc"
            }

            r = requests.post(
                "https://api.leboncoin.fr/finder/classified/search",
                headers={
                    **HEADERS,
                    'Content-Type': 'application/json',
                    'api_key': 'ba0c2dad52b3565c9a46859a28f5df23',
                    'Origin': 'https://www.leboncoin.fr',
                    'Referer': 'https://www.leboncoin.fr/annonces/offres/ventes_immobilieres/',
                },
                json=payload,
                timeout=20
            )

            if r.status_code != 200:
                time.sleep(2)
                continue

            ads = r.json().get('ads', [])
            print(f"  Dep {dep}: {len(ads)} annonces")

            for ad in ads:
                try:
                    prix = ad.get('price', [0])[0] if ad.get('price') else 0
                    if not prix or prix < 20000: continue

                    attrs = {}
                    for a in ad.get('attributes', []):
                        attrs[a['key']] = a.get('value_label') or (a.get('values', [''])[0] if a.get('values') else '')

                    surface = int(re.sub(r'[^\d]', '', str(attrs.get('square', '0'))) or 30)
                    if surface < 10: surface = 30

                    loc = ad.get('location', {})
                    ville = loc.get('city', '') or loc.get('city_label', '') or f'Département {dep}'
                    cp = loc.get('zipcode', '') or f'{dep}000'

                    img = ''
                    imgs = ad.get('images', {})
                    if imgs.get('urls_large'): img = imgs['urls_large'][0]
                    elif imgs.get('thumb_url'): img = imgs['thumb_url']

                    renta = calc_renta(prix, surface)
                    cashflow = calc_cashflow(prix, surface)
                    score = calc_score(renta, cashflow)

                    annonces.append({
                        'source': 'LeBonCoin',
                        'titre': (ad.get('subject') or f"Bien à {ville}")[:120],
                        'description': (ad.get('body') or '')[:400],
                        'prix': prix,
                        'surface': surface,
                        'ville': ville,
                        'code_postal': cp,
                        'rentabilite': renta,
                        'cashflow': cashflow,
                        'prix_m2': round(prix / surface) if surface > 0 else 0,
                        'score': score,
                        'url_original': ad.get('url', ''),
                        'image_url': img,
                        'est_particulier': ad.get('owner', {}).get('type') == 'private',
                        'type_bien': attrs.get('real_estate_type', 'Appartement'),
                        'pieces': attrs.get('rooms', ''),
                    })
                except:
                    continue

            time.sleep(2)

        except Exception as e:
            print(f"  LBC dep {dep}: {e}")

    print(f"  → LeBonCoin total: {len(annonces)}")
    return annonces

# ══ BIENICI — toute la France par département ══
def scrape_bienici():
    print("→ BienIci (toute la France)...")
    annonces = []

    for dep in DEPARTEMENTS:
        try:
            params = {
                'filters': json.dumps({
                    "size": 100,
                    "from": 0,
                    "sortBy": "publicationDate",
                    "sortOrder": "desc",
                    "onTheMarket": [True],
                    "adTypes": ["sale"],
                    "propertyType": ["flat","house","building","land","parking","loft","castle","office"],
                    "departmentCode": [dep],
                    "maxPrice": 2000000,
                    "minArea": 10
                })
            }

            r = requests.get(
                "https://www.bienici.com/realEstateAds.json",
                params=params,
                headers={**HEADERS, 'Referer': 'https://www.bienici.com/'},
                timeout=20
            )

            if r.status_code != 200:
                time.sleep(2)
                continue

            ads = r.json().get('realEstateAds', [])
            print(f"  Dep {dep}: {len(ads)} annonces")

            for ad in ads:
                try:
                    prix = ad.get('price', 0)
                    if not prix or prix < 20000: continue

                    surface = int(ad.get('surfaceArea') or ad.get('area') or 30)
                    if surface < 10: surface = 30

                    ville = ad.get('city') or ad.get('postalCode', f'Dep {dep}')
                    cp = ad.get('postalCode', '')

                    photos = ad.get('photos', [])
                    img = photos[0].get('url', '') if photos else ''

                    renta = calc_renta(prix, surface)
                    cashflow = calc_cashflow(prix, surface)
                    score = calc_score(renta, cashflow)

                    annonces.append({
                        'source': 'BienIci',
                        'titre': (ad.get('title') or f"{ad.get('propertyType','Bien')} à {ville}")[:120],
                        'description': (ad.get('description') or '')[:400],
                        'prix': int(prix),
                        'surface': surface,
                        'ville': str(ville),
                        'code_postal': str(cp),
                        'rentabilite': renta,
                        'cashflow': cashflow,
                        'prix_m2': round(int(prix) / surface) if surface > 0 else 0,
                        'score': score,
                        'url_original': f"https://www.bienici.com/annonce/{ad.get('id','')}",
                        'image_url': img,
                        'est_particulier': ad.get('userRelativeData', {}).get('isFromPrivatePerson', False),
                        'type_bien': (ad.get('propertyType') or 'Appartement').capitalize(),
                        'pieces': ad.get('roomsQuantity', ''),
                        'dpe': ad.get('energyClassification', ''),
                    })
                except:
                    continue

            time.sleep(2)

        except Exception as e:
            print(f"  BI dep {dep}: {e}")

    print(f"  → BienIci total: {len(annonces)}")
    return annonces

# ══ PAP — toute la France ══
def scrape_pap():
    print("→ PAP (toute la France)...")
    annonces = []

    # PAP permet de chercher par région
    regions = [
        'ile-de-france', 'provence-alpes-cote-d-azur', 'auvergne-rhone-alpes',
        'occitanie', 'nouvelle-aquitaine', 'hauts-de-france', 'bretagne',
        'pays-de-la-loire', 'grand-est', 'normandie', 'bourgogne-franche-comte',
        'centre-val-de-loire', 'corse', 'dom-tom'
    ]

    for region in regions:
        try:
            url = f"https://www.pap.fr/annonce/ventes-immobilieres-{region}?surface-min=10&prix-max=2000000"
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                time.sleep(2)
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.select('article, .search-list-item, [class*="item-annonce"]')
            print(f"  PAP {region}: {len(cards)} annonces")

            for card in cards[:50]:
                try:
                    titre_el = card.select_one('h2, h3, [class*="title"]')
                    titre = titre_el.get_text(strip=True) if titre_el else f'Bien en {region}'

                    prix_el = card.select_one('[class*="price"], [class*="prix"]')
                    prix_txt = prix_el.get_text(strip=True) if prix_el else '0'
                    prix = int(re.sub(r'[^\d]', '', prix_txt) or 0)
                    if prix < 20000 or prix > 2000000: continue

                    surf_el = card.select_one('[class*="surface"], [class*="area"]')
                    surf_txt = surf_el.get_text(strip=True) if surf_el else ''
                    surface = int(re.sub(r'[^\d]', '', surf_txt.split('m')[0]) or 30)
                    if surface < 10: surface = 30

                    img_el = card.select_one('img')
                    img = (img_el.get('src') or img_el.get('data-src') or '') if img_el else ''

                    link = card.select_one('a[href]')
                    url_orig = ('https://www.pap.fr' + link['href']) if link and link.get('href','').startswith('/') else ''

                    loc_el = card.select_one('[class*="location"], [class*="ville"], [class*="city"]')
                    ville = loc_el.get_text(strip=True) if loc_el else region.replace('-', ' ').title()

                    renta = calc_renta(prix, surface)
                    cashflow = calc_cashflow(prix, surface)
                    score = calc_score(renta, cashflow)

                    annonces.append({
                        'source': 'PAP',
                        'titre': titre[:120],
                        'description': '',
                        'prix': prix,
                        'surface': surface,
                        'ville': ville[:50],
                        'code_postal': '',
                        'rentabilite': renta,
                        'cashflow': cashflow,
                        'prix_m2': round(prix / surface) if surface > 0 else 0,
                        'score': score,
                        'url_original': url_orig,
                        'image_url': img,
                        'est_particulier': True,
                        'type_bien': 'Appartement',
                    })
                except:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  PAP {region}: {e}")

    print(f"  → PAP total: {len(annonces)}")
    return annonces

# ══ SELOGER — toute la France par département ══
def scrape_seloger():
    print("→ SeLoger (toute la France)...")
    annonces = []

    for dep in DEPARTEMENTS:
        try:
            url = f"https://www.seloger.com/list.htm?types=2,4&projects=2&enterprise=0&natures=1,2,4&places=[{{dep:{dep}}}]&price=NaN/2000000&surface=10/NaN&ANNONCETypes=1"

            r = requests.get(url, headers={
                **HEADERS,
                'Referer': 'https://www.seloger.com/',
            }, timeout=20)

            if r.status_code != 200:
                time.sleep(2)
                continue

            soup = BeautifulSoup(r.text, 'html.parser')

            # SeLoger embarque ses données dans des balises script JSON
            found = 0
            for script in soup.find_all('script'):
                txt = script.string or ''
                if 'classified' not in txt and 'listing' not in txt:
                    continue
                # Chercher les blocs JSON d'annonces
                matches = re.findall(r'\{[^{}]*"price"[^{}]*"surface"[^{}]*\}', txt)
                for m in matches:
                    try:
                        ad = json.loads(m)
                        prix = ad.get('price', 0)
                        surface = ad.get('surface', 30)
                        if not prix or prix < 20000: continue
                        if surface < 10: surface = 30

                        renta = calc_renta(prix, surface)
                        cashflow = calc_cashflow(prix, surface)
                        score = calc_score(renta, cashflow)

                        annonces.append({
                            'source': 'SeLoger',
                            'titre': (ad.get('title') or f'Bien dep {dep}')[:120],
                            'description': (ad.get('description') or '')[:400],
                            'prix': int(prix),
                            'surface': int(surface),
                            'ville': ad.get('city') or f'Département {dep}',
                            'code_postal': ad.get('zipCode') or ad.get('postalCode') or '',
                            'rentabilite': renta,
                            'cashflow': cashflow,
                            'prix_m2': round(int(prix) / int(surface)) if int(surface) > 0 else 0,
                            'score': score,
                            'url_original': ad.get('permalink') or ad.get('url') or '',
                            'image_url': ad.get('photo') or ad.get('image') or '',
                            'est_particulier': False,
                            'type_bien': 'Appartement',
                        })
                        found += 1
                    except:
                        continue

            # Si pas de JSON trouvé — scraper le HTML
            if found == 0:
                cards = soup.select('[data-listing-id], article, [class*="Card"]')
                for card in cards[:30]:
                    try:
                        prix_el = card.select_one('[class*="price"], [class*="Price"]')
                        prix_txt = prix_el.get_text(strip=True) if prix_el else '0'
                        prix = int(re.sub(r'[^\d]', '', prix_txt) or 0)
                        if prix < 20000: continue

                        surf_el = card.select_one('[class*="surface"], [class*="Surface"]')
                        surf_txt = surf_el.get_text(strip=True) if surf_el else ''
                        surface = int(re.sub(r'[^\d]', '', surf_txt.split('m')[0]) or 30)

                        titre_el = card.select_one('h2, h3, [class*="title"]')
                        titre = titre_el.get_text(strip=True) if titre_el else f'Bien dep {dep}'

                        img_el = card.select_one('img')
                        img = (img_el.get('src') or img_el.get('data-src') or '') if img_el else ''

                        link = card.select_one('a[href]')
                        url_orig = link['href'] if link else ''
                        if url_orig and not url_orig.startswith('http'):
                            url_orig = 'https://www.seloger.com' + url_orig

                        renta = calc_renta(prix, surface)
                        cashflow = calc_cashflow(prix, surface)
                        score = calc_score(renta, cashflow)

                        annonces.append({
                            'source': 'SeLoger',
                            'titre': titre[:120],
                            'description': '',
                            'prix': prix,
                            'surface': surface,
                            'ville': f'Département {dep}',
                            'code_postal': '',
                            'rentabilite': renta,
                            'cashflow': cashflow,
                            'prix_m2': round(prix / surface) if surface > 0 else 0,
                            'score': score,
                            'url_original': url_orig,
                            'image_url': img,
                            'est_particulier': False,
                            'type_bien': 'Appartement',
                        })
                    except:
                        continue

            print(f"  SeLoger dep {dep}: {found or len(cards if found==0 else [])} annonces")
            time.sleep(3)

        except Exception as e:
            print(f"  SL dep {dep}: {e}")

    print(f"  → SeLoger total: {len(annonces)}")
    return annonces

# ══ MAIN ══
def main():
    print(f"\n{'='*60}")
    print(f"PropScan Scraper — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Couverture: France entière ({len(DEPARTEMENTS)} départements)")
    print(f"{'='*60}")

    all_annonces = []

    lbc = scrape_leboncoin()
    all_annonces.extend(lbc)

    bi = scrape_bienici()
    all_annonces.extend(bi)

    pap = scrape_pap()
    all_annonces.extend(pap)

    sl = scrape_seloger()
    all_annonces.extend(sl)

    print(f"\n📦 Total: {len(all_annonces)} annonces à insérer")

    ok = 0
    for a in all_annonces:
        if supabase_insert(a):
            ok += 1
        if ok % 100 == 0 and ok > 0:
            print(f"  {ok} insérées...")

    print(f"\n✅ {ok}/{len(all_annonces)} insérées dans Supabase")
    print(f"⏳ Pause 30 minutes...\n")
    time.sleep(1800)

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(f"Erreur critique: {e}")
            time.sleep(60)

# Cette ligne est un marqueur — le vrai ajout est dans le fichier principal
