"""Name and address normalisation shared by venue_companies.py and name_companies.py."""
import re

PC = re.compile(r'\b([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})\b')
STOP = r'\b(ltd|limited|llp|plc|uk|london|the|and|co|company|group|holdings|trading|restaurant|restaurants|cafe|café|bar|kitchen|hospitality|services|catering|richmond|shoreditch|hoxton)\b'
GENERIC = {'pizza', 'coffee', 'bakery', 'grill', 'food', 'foods', 'deli', 'pub', 'express', 'chicken', 'burger', 'sushi', 'thai', 'indian', 'noodle', 'tea', 'wine', 'venue', 'house', 'street', 'cafe', 'bistro', 'lounge', 'social', 'club', 'tavern', 'inn', 'arms', 'dining', 'eatery', 'peri', 'spice', 'charcoal', 'kebab'}
LONDON = re.compile(r'^(E|EC|N|NW|SE|SW|W|WC|TW|KT|CR|BR|HA|UB|EN|IG|RM|DA|SM)\d')

def postcode(s):
    m = PC.search((s or '').upper()); return f'{m.group(1)} {m.group(2)}' if m else None

def number(addr):
    """House number from the first address line, skipping 'Flat 2,' / 'Unit 5' prefixes."""
    first = re.sub(r'^(flat|unit|suite|office|studio)\s+\S+[, ]+', '', (addr or '').split(',')[0].strip(), flags=re.I)
    m = re.match(r'(\d+[a-z]?)', first.lower()); return m.group(1) if m else None

def words(s): return ' '.join(re.sub(STOP, ' ', re.sub(r'[^a-z0-9 ]', ' ', re.sub(r"['’]", '', (s or '').lower()).replace('&', ' and '))).split())

def distinctive(w):
    """Long enough to identify a business: two or more words, or one uncommon word of 7+ letters."""
    return not set(w.split()) <= GENERIC and (len(w.split()) >= 2 and len(w) >= 6 or len(w) >= 7)

def close(a, b):
    """Words-level match: equal, or one name inside the other when the shorter one has two or more words
    ('bite me baby' inside 'bite me baby cafe and bar'); a single word like 'saffron' must match exactly."""
    if len(a) < 3 or len(b) < 3: return 0
    if a == b: return 1.0
    short, long_ = sorted((a, b), key=len)
    return 0.9 if len(short.split()) >= 2 and distinctive(short) and f' {short} ' in f' {long_} ' else 0
