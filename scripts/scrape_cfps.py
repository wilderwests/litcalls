#!/usr/bin/env python3
"""
Literary CFP Scraper — Massive aggregator of publication calls
(journal articles, book chapters, edited volumes, monograph proposals)
in literary studies worldwide, including Spanish/Hispanic sources.

Excludes conference-only CFPs. Runs daily via GitHub Actions.
"""

import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import hashlib

OUTPUT_DIR = Path(__file__).parent.parent / "public" / "data"
OUTPUT_FILE = OUTPUT_DIR / "cfps.json"

# ═══════════════════════════════════════════════════════════════
# TOPIC TAXONOMY — expandable by the user
# ═══════════════════════════════════════════════════════════════

TOPICS = {
    "fantastic": {
        "label": "The Fantastic / Gothic / Speculative",
        "keywords": [
            "fantastic literature", "fantasy literature", "gothic literature",
            "gothic fiction", "gothic studies", "speculative fiction",
            "science fiction", "the uncanny", "weird fiction",
            "the marvelous", "lo fantástico", "literatura fantástica",
            "ciencia ficción", "ficción especulativa", "gótico",
            "horror literature", "supernatural", "utopia", "dystopia",
            "fairy tale", "fairy tales", "lo maravilloso", "lo insólito",
            "fantasy studies", "dark fantasy", "new weird",
            "urban fantasy", "magical realism", "realismo mágico",
            "lo neofantástico", "literatura de terror",
        ],
    },
    "ecocriticism": {
        "label": "Ecocriticism / Environmental Humanities",
        "keywords": [
            "ecocriticism", "environmental humanities", "ecological criticism",
            "green studies", "climate fiction", "cli-fi", "nature writing",
            "environmental literature", "anthropocene", "eco-gothic",
            "ecopoetics", "ecofeminism", "environmental justice",
            "sustainability", "post-natural", "dark ecology",
            "ecocrítica", "humanidades ambientales", "ecología",
            "literatura y medio ambiente", "naturaleza", "ecofeminismo",
            "cambio climático", "estudios medioambientales",
            "plant studies", "vegetal", "botanical",
        ],
    },
    "human-animal": {
        "label": "Human-Animal Studies / Posthumanism",
        "keywords": [
            "human animal studies", "human-animal", "critical animal studies",
            "posthumanism", "posthumanist", "animal ethics",
            "interspecies", "zoopoetics", "animality",
            "multispecies", "more-than-human", "nonhuman",
            "animal turn", "animal literature", "animal rights",
            "estudios animales", "posthumanismo", "animalidad",
            "estudios humano-animal", "zoocrítica",
            "new materialism", "object-oriented ontology",
            "creaturely", "beastly", "bestiary",
        ],
    },
    "postcolonial": {
        "label": "Postcolonial / World Literature",
        "keywords": [
            "postcolonial", "decolonial", "world literature",
            "global south", "subaltern", "diaspora",
            "transcultural", "transnational literature",
            "literatura postcolonial", "decolonialidad",
            "orientalism", "migration literature", "exile",
        ],
    },
    "gender": {
        "label": "Gender / Feminist / Queer Studies",
        "keywords": [
            "gender studies", "feminist criticism", "queer theory",
            "queer studies", "women's writing", "masculinities",
            "lgbtq", "trans studies", "feminist literary",
            "estudios de género", "feminismo", "teoría queer",
            "escritura femenina", "ginocrítica",
        ],
    },
    "digital": {
        "label": "Digital Humanities / Media",
        "keywords": [
            "digital humanities", "electronic literature", "e-literature",
            "new media", "computational", "distant reading",
            "digital literature", "humanidades digitales",
            "literatura digital", "intermediality", "transmedia",
            "videogame", "game studies", "ludology",
        ],
    },
    "medieval-early": {
        "label": "Medieval / Early Modern",
        "keywords": [
            "medieval literature", "medieval studies", "middle ages",
            "early modern", "renaissance literature", "renaissance studies",
            "siglo de oro", "edad media", "literatura medieval",
            "manuscrito", "philology", "filología",
            "old english", "chaucer", "arthurian",
        ],
    },
    "modern-contemporary": {
        "label": "Modern / Contemporary Literature",
        "keywords": [
            "modernism", "modernist", "contemporary literature",
            "contemporary fiction", "twentieth century", "21st century",
            "contemporary poetry", "experimental fiction",
            "literatura contemporánea", "narrativa actual",
            "autofiction", "autoficción", "posmodernismo",
        ],
    },
    "theory": {
        "label": "Literary Theory / Comparative",
        "keywords": [
            "literary theory", "comparative literature", "narratology",
            "hermeneutics", "aesthetics", "affect theory",
            "reader response", "reception theory", "cognitive poetics",
            "teoría literaria", "literatura comparada", "narratología",
            "estética", "teoría crítica", "semiótica",
        ],
    },
    "hispanic": {
        "label": "Hispanic / Latin American Studies",
        "keywords": [
            "hispanic studies", "latin american literature",
            "estudios hispánicos", "literatura hispanoamericana",
            "literatura española", "spanish literature",
            "literatura latinoamericana", "filología hispánica",
            "letras hispánicas", "hispanismo", "cervantes",
            "literatura iberoamericana", "peninsular",
        ],
    },
    "english": {
        "label": "English / Anglophone Literature",
        "keywords": [
            "english literature", "anglophone", "british literature",
            "american literature", "victorian", "romantic period",
            "eighteenth century literature", "postwar british",
            "contemporary british", "irish literature",
            "canadian literature", "australian literature",
        ],
    },
    "other-languages": {
        "label": "French / German / Italian / Other",
        "keywords": [
            "french literature", "littérature française", "germanistik",
            "german literature", "italian literature", "letteratura",
            "slavic literature", "scandinavian literature",
            "portuguese literature", "literatura portuguesa",
            "lusophone", "francophone", "arabic literature",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════
# PUBLICATION TYPE DETECTION
# ═══════════════════════════════════════════════════════════════

CONFERENCE_MARKERS = [
    "conference paper", "conference presentation", "symposium presentation",
    "panel proposal", "roundtable", "annual meeting",
    "congreso", "jornadas", "simposio", "coloquio",
    "workshop proposal", "poster session",
]

PUBLICATION_MARKERS = [
    "journal", "special issue", "edited volume", "edited collection",
    "book chapter", "chapter proposal", "monograph",
    "revista", "número especial", "volumen editado",
    "capítulo", "monografía", "propuesta de libro",
    "call for articles", "call for chapters", "call for contributions",
    "call for essays", "call for submissions", "manuscript",
    "articles", "essays", "peer-reviewed", "peer reviewed",
    "book proposal", "volume", "anthology",
    "convocatoria de artículos", "envío de artículos",
    "propuestas de capítulo", "dossier", "sección monográfica",
]

PUB_TYPES = {
    "journal": [
        "journal", "special issue", "revista", "número especial",
        "call for articles", "peer-reviewed", "peer reviewed",
        "dossier", "sección monográfica", "open issue",
        "themed issue", "thematic issue",
    ],
    "chapter": [
        "edited volume", "edited collection", "book chapter",
        "chapter proposal", "call for chapters", "anthology",
        "volumen editado", "capítulo", "propuestas de capítulo",
        "call for contributions to a volume",
    ],
    "monograph": [
        "monograph", "book proposal", "book manuscript",
        "monografía", "propuesta de libro", "book-length",
        "series editor", "book series",
    ],
}

# ═══════════════════════════════════════════════════════════════
# IMPACT FACTOR DATABASE (approximate, for classification)
# ═══════════════════════════════════════════════════════════════

VENUE_IMPACT = {
    # --- HIGH (IF > 2.0 or Q1 in Arts & Humanities) ---
    "new literary history": ("high", "Q1"),
    "pmla": ("high", "Q1"),
    "critical inquiry": ("high", "Q1"),
    "american literature": ("high", "Q1"),
    "modern language review": ("high", "Q1"),
    "environmental humanities": ("high", "Q1"),
    "isle": ("high", "Q1"),
    "society & animals": ("high", "Q1"),
    "society and animals": ("high", "Q1"),
    "comparative literature": ("high", "Q1"),
    "narrative": ("high", "Q1"),
    "novel: a forum on fiction": ("high", "Q1"),
    "poetics today": ("high", "Q1"),
    "journal of world literature": ("high", "Q1"),
    "world literature today": ("high", "Q1"),
    "signs": ("high", "Q1"),
    "differences": ("high", "Q1"),
    "glq": ("high", "Q1"),
    "new left review": ("high", "Q1"),
    "nineteenth-century literature": ("high", "Q1"),
    "victorian studies": ("high", "Q1"),
    "english literary history": ("high", "Q1"),
    "elh": ("high", "Q1"),
    "representations": ("high", "Q1"),
    "diacritics": ("high", "Q1"),
    # --- MEDIUM (Q2 / solid indexed) ---
    "green letters": ("medium", "Q2"),
    "science fiction studies": ("medium", "Q2"),
    "journal of the fantastic in the arts": ("medium", "Q2"),
    "extrapolation": ("medium", "Q2"),
    "gothic studies": ("medium", "Q2"),
    "textual practice": ("medium", "Q2"),
    "humanimalia": ("medium", "Q2"),
    "journal of postcolonial writing": ("medium", "Q2"),
    "studies in the novel": ("medium", "Q2"),
    "women's studies": ("medium", "Q2"),
    "configurations": ("medium", "Q2"),
    "mosaic": ("medium", "Q2"),
    "postcolonial studies": ("medium", "Q2"),
    "ariel": ("medium", "Q2"),
    "journal of commonwealth literature": ("medium", "Q2"),
    "style": ("medium", "Q2"),
    "studies in romanticism": ("medium", "Q2"),
    "modernism/modernity": ("medium", "Q2"),
    "contemporary literature": ("medium", "Q2"),
    "review of english studies": ("medium", "Q2"),
    "english studies": ("medium", "Q2"),
    "cervantes": ("medium", "Q2"),
    "bulletin of hispanic studies": ("medium", "Q2"),
    "bulletin of spanish studies": ("medium", "Q2"),
    "hispanic review": ("medium", "Q2"),
    "modern language notes": ("medium", "Q2"),
    "romance quarterly": ("medium", "Q2"),
    "hispania": ("medium", "Q2"),
    "revista de literatura": ("medium", "Q2"),
    # --- LOW (Q3-Q4 / emerging) ---
    "femspec": ("low", "Q3-Q4"),
    "foundation": ("low", "Q3-Q4"),
    "journal of ecocriticism": ("low", "Q3-Q4"),
    "antennae": ("low", "Q3-Q4"),
    "paranormal review": ("low", "Q3-Q4"),
    "journal of the short story in english": ("low", "Q3-Q4"),
    "brumal": ("low", "Q3-Q4"),
    "tropelías": ("low", "Q3-Q4"),
    "signa": ("low", "Q3-Q4"),
    "castilla": ("low", "Q3-Q4"),
    "tonos digital": ("low", "Q3-Q4"),
    "impossibilia": ("low", "Q3-Q4"),
    "tenso diagonal": ("low", "Q3-Q4"),
    "álabe": ("low", "Q3-Q4"),
    "dicenda": ("low", "Q3-Q4"),
    "epos": ("low", "Q3-Q4"),
    "anales de literatura española": ("low", "Q3-Q4"),
}

VOLUME_PUBLISHERS = [
    "routledge", "palgrave", "bloomsbury", "peter lang",
    "edinburgh university press", "cambridge scholars",
    "lexington", "mcfarland", "anthem press", "de gruyter",
    "brill", "john benjamins", "transcript verlag",
    "cátedra", "iberoamericana", "vervuert", "akal",
    "arco libros", "castalia", "visor", "pre-textos",
    "comares", "síntesis", "tirant humanidades",
    "universidad", "university press",
]


# ═══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def clean_html(text):
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Academic CFP Tracker; literary research)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] {url}: {e}")
        return None


def make_id(title, venue=""):
    raw = f"{title}{venue}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def is_publication_call(text):
    """Return True if this looks like a publication call, not a conference."""
    t = text.lower()
    pub_score = sum(1 for m in PUBLICATION_MARKERS if m in t)
    conf_score = sum(1 for m in CONFERENCE_MARKERS if m in t)
    # If explicitly a conference with no publication markers, skip
    if conf_score > 0 and pub_score == 0:
        return False
    # Accept anything with publication markers, or ambiguous
    return True


def classify_topics(text):
    t = text.lower()
    found = []
    for topic_id, topic_data in TOPICS.items():
        for kw in topic_data["keywords"]:
            if kw in t:
                found.append(topic_id)
                break
    return found if found else ["general"]


def classify_pub_type(text):
    t = text.lower()
    for ptype, markers in PUB_TYPES.items():
        for m in markers:
            if m in t:
                return ptype
    return "unknown"


def classify_impact(venue_text):
    if not venue_text:
        return "unknown", None
    v = venue_text.lower()
    for name, (tier, quartile) in VENUE_IMPACT.items():
        if name in v:
            return tier, quartile
    for pub in VOLUME_PUBLISHERS:
        if pub in v:
            return "unknown", "Edited volume"
    if "journal" in v or "revista" in v or "review" in v:
        return "low", "Indexed"
    return "unknown", None


def extract_deadline(text):
    patterns = [
        r"deadline[:\s]*(\d{1,2}[\s/\-\.]\w+[\s/\-\.]\d{4})",
        r"deadline[:\s]*(\w+\s+\d{1,2},?\s*\d{4})",
        r"fecha\s*l[ií]mite[:\s]*(\d{1,2}[\s/\-\.]\w+[\s/\-\.]\d{4})",
        r"plazo[:\s]*(\d{1,2}[\s/\-\.]\w+[\s/\-\.]\d{4})",
        r"due[:\s]*(\w+\s+\d{1,2},?\s*\d{4})",
        r"by\s+(\w+\s+\d{1,2},?\s*\d{4})",
        r"(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})",
        r"(\d{1,2}\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{4})",
    ]
    t = text.lower()
    for p in patterns:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


# ═══════════════════════════════════════════════════════════════
# SCRAPERS
# ═══════════════════════════════════════════════════════════════

def scrape_wikicfp():
    """WikiCFP — filter for publication-only calls."""
    print("Scraping WikiCFP...")
    cfps = []
    terms = [
        "literary+studies", "literature+special+issue",
        "ecocriticism", "gothic+literature", "fantastic+literature",
        "animal+studies+literature", "posthumanism+literature",
        "postcolonial+literature", "comparative+literature",
        "hispanic+literature", "spanish+literature",
        "english+literature+special+issue", "edited+volume+literature",
        "digital+humanities+literature", "gender+literature",
        "medieval+literature", "contemporary+fiction",
        "world+literature", "queer+literature",
        "book+chapter+literature", "literary+theory",
        "french+literature", "german+literature",
        "science+fiction+studies", "call+for+chapters+literature",
    ]

    for term in terms:
        url = f"http://www.wikicfp.com/cfp/servlet/tool.search?q={term}&year=f"
        html = fetch_url(url)
        if not html:
            continue

        rows = re.findall(
            r'<tr[^>]*>.*?<a\s+href="([^"]*)"[^>]*>([^<]+)</a>.*?'
            r'<td[^>]*>([^<]*)</td>.*?<td[^>]*>([^<]*)</td>',
            html, re.DOTALL
        )

        for link, title, dates, location in rows:
            title = clean_html(title)
            full = f"{title} {dates} {location}"
            if not is_publication_call(full):
                continue
            topics = classify_topics(full)
            cfp_url = f"http://www.wikicfp.com{link}" if link.startswith("/") else link

            cfps.append({
                "title": title,
                "description": f"WikiCFP listing. {clean_html(location).strip()}".strip(),
                "venue": "",
                "deadline": clean_html(dates).strip() or None,
                "url": cfp_url,
                "topics": topics,
                "pubType": classify_pub_type(full),
                "source": "WikiCFP",
            })

    print(f"  → {len(cfps)} publication CFPs from WikiCFP")
    return cfps


def scrape_hnet():
    """H-Net discussion networks — literary & humanities CFPs."""
    print("Scraping H-Net...")
    cfps = []

    feeds = [
        "https://networks.h-net.org/h-environment/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-animal/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-literary/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-sci-med-tech/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-gothic/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-women/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-latam/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-spain/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-france/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-german/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-asia/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-africa/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-albion/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-mediterranean/discussions?filter=cfp&format=rss",
        "https://networks.h-net.org/h-postcolonial/discussions?filter=cfp&format=rss",
    ]

    for feed_url in feeds:
        xml_text = fetch_url(feed_url)
        if not xml_text:
            continue
        try:
            root = ET.fromstring(xml_text)
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                desc = item.findtext("description") or ""
                link = (item.findtext("link") or "").strip()

                full = f"{title} {clean_html(desc)}"
                if not is_publication_call(full):
                    continue

                topics = classify_topics(full)
                deadline = extract_deadline(full)
                description = clean_html(desc)[:350]
                if len(description) > 345:
                    description = description[:345] + "…"

                cfps.append({
                    "title": clean_html(title),
                    "description": description,
                    "venue": "H-Net",
                    "deadline": deadline,
                    "url": link,
                    "topics": topics,
                    "pubType": classify_pub_type(full),
                    "source": "H-Net",
                })
        except ET.ParseError:
            pass

    print(f"  → {len(cfps)} publication CFPs from H-Net")
    return cfps


def scrape_penn_cfp():
    """UPenn CFP list."""
    print("Scraping Penn CFP...")
    cfps = []
    url = "https://call-for-papers.sas.upenn.edu/"
    html = fetch_url(url)
    if not html:
        return cfps

    entries = re.findall(r'<a\s+href="([^"]*)"[^>]*>\s*([^<]{15,300})\s*</a>', html, re.DOTALL)
    for link, title in entries:
        title = clean_html(title)
        if not is_publication_call(title):
            continue
        topics = classify_topics(title)
        full_url = link if link.startswith("http") else f"https://call-for-papers.sas.upenn.edu/{link.lstrip('/')}"
        cfps.append({
            "title": title,
            "description": "Listed on the University of Pennsylvania CFP site.",
            "venue": "Penn CFP",
            "deadline": extract_deadline(title),
            "url": full_url,
            "topics": topics,
            "pubType": classify_pub_type(title),
            "source": "Penn CFP",
        })

    print(f"  → {len(cfps)} from Penn CFP")
    return cfps


def scrape_cfplist():
    """cfplist.com categories."""
    print("Scraping cfplist.com...")
    cfps = []
    categories = [
        "literature", "cultural-studies", "environment",
        "gender-studies", "philosophy", "history",
    ]
    for cat in categories:
        html = fetch_url(f"https://www.cfplist.com/browse/{cat}")
        if not html:
            continue
        entries = re.findall(
            r'<a\s+href="(/cfp/[^"]+)"[^>]*>([^<]+)</a>',
            html, re.DOTALL
        )
        for link, title in entries:
            title = clean_html(title)
            if not is_publication_call(title):
                continue
            topics = classify_topics(title)
            cfps.append({
                "title": title,
                "description": "Listed on cfplist.com.",
                "venue": "cfplist.com",
                "deadline": None,
                "url": f"https://www.cfplist.com{link}",
                "topics": topics,
                "pubType": classify_pub_type(title),
                "source": "cfplist",
            })

    print(f"  → {len(cfps)} from cfplist.com")
    return cfps


def scrape_dialnet():
    """Dialnet — Spanish academic portal. Scrape their CFP / news section."""
    print("Scraping Dialnet / Spanish sources...")
    cfps = []

    # Dialnet doesn't have a dedicated CFP feed, but we can search
    search_terms = [
        "convocatoria+artículos+literatura",
        "call+for+papers+literatura+española",
        "número+especial+revista+filología",
        "convocatoria+capítulos+libro+literatura",
    ]

    for term in search_terms:
        url = f"https://dialnet.unirioja.es/buscar/documentos?querysDismax.DOCUMENTOS_TODO={term}"
        html = fetch_url(url)
        if not html:
            continue

        entries = re.findall(
            r'<a\s+href="(/servlet/articulo\?codigo=[^"]+)"[^>]*>\s*([^<]{15,250})\s*</a>',
            html, re.DOTALL
        )
        for link, title in entries[:5]:
            title = clean_html(title)
            topics = classify_topics(title)
            cfps.append({
                "title": title,
                "description": "Found on Dialnet (Spanish academic database).",
                "venue": "Dialnet",
                "deadline": None,
                "url": f"https://dialnet.unirioja.es{link}",
                "topics": topics,
                "pubType": classify_pub_type(title),
                "source": "Dialnet",
            })

    # Also scrape known Spanish literary journal CFP pages
    spanish_journals = [
        ("https://revistas.ucm.es/index.php/DICE/announcement", "Dicenda (UCM)"),
        ("https://revistas.uam.es/actionova/announcement", "Actio Nova (UAM)"),
        ("https://revistas.um.es/tonos/announcement", "Tonos Digital (UM)"),
        ("https://revistas.unizar.es/index.php/tropelias/announcement", "Tropelías (Unizar)"),
        ("https://revistes.uab.cat/brumal/announcement", "Brumal (UAB)"),
    ]

    for url, name in spanish_journals:
        html = fetch_url(url)
        if not html:
            continue
        # OJS announcement pages have a common structure
        entries = re.findall(
            r'<h[34][^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>\s*([^<]+)</a>',
            html, re.DOTALL
        )
        for link, title in entries:
            title = clean_html(title)
            full = f"{title} {name}"
            if not any(kw in full.lower() for kw in [
                "call", "convocatoria", "cfp", "artículo", "envío",
                "propuesta", "número", "dossier", "monográfico"
            ]):
                continue
            topics = classify_topics(full)
            cfps.append({
                "title": f"{title} — {name}",
                "description": f"Call from {name}.",
                "venue": name,
                "deadline": extract_deadline(title),
                "url": link if link.startswith("http") else f"{url.rsplit('/', 1)[0]}/{link.lstrip('/')}",
                "topics": topics,
                "pubType": "journal",
                "source": "Spanish journal",
            })

    print(f"  → {len(cfps)} from Spanish sources")
    return cfps


def scrape_ojs_portals():
    """Scrape Open Journal Systems portals for announcements."""
    print("Scraping OJS portals...")
    cfps = []

    # Major OJS portals with literary journals
    portals = [
        ("https://www.degruyter.com/search?query=call+for+papers+literature&type=journal", "De Gruyter"),
        ("https://ojs.uv.es/index.php/SRELS/announcement", "Srels (UV)"),
    ]

    # This is a lighter approach — just check known announcement pages
    for url, name in portals:
        html = fetch_url(url)
        if not html:
            continue
        entries = re.findall(
            r'<a[^>]*href="([^"]*)"[^>]*>\s*([^<]{15,200})\s*</a>',
            html, re.DOTALL
        )
        for link, title in entries[:10]:
            title = clean_html(title)
            full = f"{title} {name}"
            if not is_publication_call(full):
                continue
            topics = classify_topics(full)
            cfps.append({
                "title": title,
                "description": f"Found on {name}.",
                "venue": name,
                "deadline": extract_deadline(title),
                "url": link if link.startswith("http") else "",
                "topics": topics,
                "pubType": classify_pub_type(full),
                "source": name,
            })

    print(f"  → {len(cfps)} from OJS portals")
    return cfps


def scrape_publisher_pages():
    """Check major publisher CFP/proposal pages."""
    print("Scraping publisher pages...")
    cfps = []

    publisher_urls = [
        ("https://www.routledge.com/search?query=call+for+chapters+literature", "Routledge"),
        ("https://www.palgrave.com/gp/series/14672", "Palgrave Studies in Animals and Literature"),
        ("https://www.bloomsbury.com/uk/academic/literary-studies/", "Bloomsbury"),
    ]

    for url, name in publisher_urls:
        html = fetch_url(url)
        if not html:
            continue
        entries = re.findall(
            r'<a[^>]*href="([^"]*)"[^>]*>\s*([^<]{15,200})\s*</a>',
            html, re.DOTALL
        )
        for link, title in entries[:8]:
            title = clean_html(title)
            full = f"{title} {name}"
            if not is_publication_call(full):
                continue
            topics = classify_topics(full)
            cfps.append({
                "title": title,
                "description": f"From {name}.",
                "venue": name,
                "deadline": extract_deadline(title),
                "url": link if link.startswith("http") else "",
                "topics": topics,
                "pubType": classify_pub_type(full),
                "source": name,
            })

    print(f"  → {len(cfps)} from publishers")
    return cfps


# ═══════════════════════════════════════════════════════════════
# DEDUP + ENRICHMENT
# ═══════════════════════════════════════════════════════════════

def deduplicate(cfps):
    seen = set()
    unique = []
    for c in cfps:
        norm = re.sub(r"[^a-z0-9]", "", c["title"].lower())[:50]
        if norm and norm not in seen:
            seen.add(norm)
            unique.append(c)
    return unique


def enrich(cfps):
    for c in cfps:
        full = f"{c.get('venue', '')} {c.get('title', '')} {c.get('description', '')}"
        tier, quartile = classify_impact(full)
        c["impactTier"] = tier
        c["impactQuartile"] = quartile
        c["id"] = make_id(c["title"], c.get("venue", ""))
        if not c.get("pubType") or c["pubType"] == "unknown":
            c["pubType"] = classify_pub_type(full)
    return cfps


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    now = datetime.now(timezone.utc)
    print(f"=== Literary CFP Scraper — {now.isoformat()} ===\n")

    all_cfps = []
    all_cfps.extend(scrape_wikicfp())
    all_cfps.extend(scrape_hnet())
    all_cfps.extend(scrape_penn_cfp())
    all_cfps.extend(scrape_cfplist())
    all_cfps.extend(scrape_dialnet())
    all_cfps.extend(scrape_ojs_portals())
    all_cfps.extend(scrape_publisher_pages())

    all_cfps = deduplicate(all_cfps)
    all_cfps = enrich(all_cfps)

    # Sort by impact tier
    tier_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    all_cfps.sort(key=lambda c: tier_order.get(c.get("impactTier", "unknown"), 4))

    # Also export the topic taxonomy for the frontend
    topic_export = {k: v["label"] for k, v in TOPICS.items()}

    output = {
        "last_updated": now.isoformat(),
        "total": len(all_cfps),
        "topics": topic_export,
        "cfps": all_cfps,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=== Done! {len(all_cfps)} publication CFPs saved ===")


if __name__ == "__main__":
    main()
