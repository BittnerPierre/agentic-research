import logging
import re
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from typing import List, Optional

# Configuration du logger
logger = logging.getLogger(__name__)


class SimpleHTMLParser(HTMLParser):
    """Parser HTML simple pour extraire le texte et les métadonnées."""
    
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
        self.title = ""
        self.in_title = False
        self.in_script = False
        self.in_style = False
        
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'title':
            self.in_title = True
        elif tag.lower() in ['script', 'style']:
            self.in_script = True
            
    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self.in_title = False
        elif tag.lower() in ['script', 'style']:
            self.in_script = False
            
    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.in_script and not self.in_style:
            # Ajouter le texte en ignorant les scripts et styles
            self.fed.append(data)
            
    def get_text(self):
        return ''.join(self.fed)
    
    def get_title(self):
        return self.title.strip()


class WebDocument:
    """Classe simple pour représenter un document web."""
    
    def __init__(self, content: str, url: str, title: str = ""):
        self.page_content = content
        self.metadata = {
            'source': url,
            'title': title or self._extract_title_from_url(url)
        }
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extrait un titre approximatif depuis l'URL."""
        path = urllib.parse.urlparse(url).path
        if path and path != '/':
            # Prendre la dernière partie du path et la nettoyer
            title = path.split('/')[-1]
            title = re.sub(r'[^a-zA-Z0-9\s-]', ' ', title)
            title = ' '.join(title.split())
            return title or "Document Web"
        return "Document Web"


def clean_text(text: str) -> str:
    """
    Nettoie le texte extrait du HTML.
    
    Args:
        text: Texte brut à nettoyer
        
    Returns:
        Texte nettoyé
    """
    # Supprimer les espaces multiples et les sauts de ligne excessifs
    text = re.sub(r'\s+', ' ', text)
    
    # Supprimer les caractères de contrôle
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normaliser les sauts de ligne
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()


def fetch_web_content(url: str, timeout: int = 30) -> Optional[WebDocument]:
    """
    Récupère le contenu d'une URL et l'analyse.
    
    Args:
        url: URL à récupérer
        timeout: Timeout en secondes
        
    Returns:
        WebDocument ou None en cas d'erreur
    """
    try:
        logger.info(f"Récupération du contenu de: {url}")
        
        # Headers pour simuler un navigateur
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        request = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                logger.error(f"Erreur HTTP {response.status} pour {url}")
                return None
                
            # Lire le contenu
            content = response.read()
            
            # Détecter l'encodage depuis les headers ou utiliser utf-8 par défaut
            encoding = 'utf-8'
            content_type = response.headers.get('Content-Type', '')
            if 'charset=' in content_type:
                encoding = content_type.split('charset=')[1].split(';')[0].strip()
            
            try:
                html_content = content.decode(encoding)
            except UnicodeDecodeError:
                # Fallback sur utf-8 avec gestion des erreurs
                html_content = content.decode('utf-8', errors='replace')
        
        # Parser le HTML
        parser = SimpleHTMLParser()
        parser.feed(html_content)
        
        # Extraire et nettoyer le texte
        text_content = parser.get_text()
        title = parser.get_title()
        
        # Nettoyer le texte
        text_content = clean_text(text_content)
        
        if not text_content.strip():
            logger.warning(f"Aucun contenu textuel extrait de {url}")
            return None
            
        logger.info(f"Contenu extrait avec succès de {url} ({len(text_content)} caractères)")
        return WebDocument(text_content, url, title)
        
    except urllib.error.URLError as e:
        logger.error(f"Erreur de connexion pour {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de {url}: {e}")
        return None


def load_documents_from_urls(urls: List[str]) -> List[WebDocument]:
    """
    Charge des documents depuis une liste d'URLs.
    
    Args:
        urls: Liste des URLs à charger
        
    Returns:
        Liste des documents chargés avec succès
    """
    documents = []
    
    for url in urls:
        doc = fetch_web_content(url)
        if doc:
            documents.append(doc)
        else:
            logger.warning(f"Impossible de charger le document de {url}")
    
    return documents
