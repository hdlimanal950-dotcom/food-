#!/usr/bin/env python3
"""
Reddit RSS Bot v3.0.0 PRODUCTION ULTIMATE
🔥 Direct Tumblr RSS + Optimized for Render.com
✅ Fixed: Direct source (no rss.app blocking)
✅ Fixed: Fast port binding (no pre-fetch delay)
✅ Fixed: Gemini API path (models/ prefix)
✅ Fixed: Clean headers (no compression issues)
✅ Multi-strategy fetching with intelligent fallbacks
"""
import os, sys, json, time, logging, hashlib, random, re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
from dataclasses import dataclass
from enum import Enum
import pickle
from pathlib import Path
from flask import Flask, Response, jsonify, request
from waitress import serve
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode

# ═══════════════════════════════════════════════════════════════════════════════
# SMART IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

# Primary: curl_cffi
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    curl_requests = None

# Secondary: requests-html
try:
    from requests_html import HTMLSession
    REQUESTS_HTML_AVAILABLE = True
except ImportError:
    REQUESTS_HTML_AVAILABLE = False
    HTMLSession = None

# Tertiary: cloudscraper
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    cloudscraper = None

# Fallback: standard requests
import requests as standard_requests

# AI Enhancement
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

# HTML Parsing
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup = None

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """إعدادات شاملة محسّنة"""
    # Application
    APP_NAME: str = "Reddit RSS Bot Ultimate"
    VERSION: str = "3.0.0"
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = int(os.getenv("PORT", 10000))
    
    # RSS Sources - ✅ FIXED: Direct Tumblr RSS
    ORIGINAL_RSS_URL: str = "https://shecooksandbakes.tumblr.com/rss"
    FALLBACK_RSS_URLS: List[str] = None
    
    # AI Configuration - ✅ FIXED: Added models/ prefix
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "models/gemini-1.5-flash"
    GEMINI_MAX_RETRIES: int = 3
    
    # Feed Configuration
    FEED_TITLE: str = "She Cooks Bakes - Professional Recipes"
    FEED_DESCRIPTION: str = "Delicious baking recipes and cooking tips"
    FEED_LINK: str = "https://shecooksandbakes.tumblr.com"
    FEED_LANGUAGE: str = "en-us"
    MAX_FEED_ITEMS: int = 10
    
    # Multi-layer Caching
    CACHE_DURATION: int = 300
    LONG_CACHE_DURATION: int = 86400
    EMERGENCY_CACHE_DURATION: int = 604800
    CACHE_FILE: str = "rss_cache_v3.pkl"
    
    # Request Configuration
    REQUEST_TIMEOUT: int = 45
    MAX_RETRIES: int = 7
    RETRY_BACKOFF: float = 2.5
    JITTER_RANGE: Tuple[float, float] = (2.0, 6.0)
    
    # Logging
    LOG_FILE: str = "reddit_rss_production.log"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5
    
    # Self-ping
    SELF_PING_ENABLED: bool = True
    SELF_PING_INTERVAL: int = 840
    
    def __post_init__(self):
        if self.FALLBACK_RSS_URLS is None:
            self.FALLBACK_RSS_URLS = []

config = Config()

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging() -> logging.Logger:
    """إعداد نظام تسجيل متقدم"""
    logger = logging.getLogger(config.APP_NAME)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(console_fmt)
    
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-25s | %(message)s'
    )
    file_handler.setFormatter(file_fmt)
    
    logger.addHandler(console)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

# ═══════════════════════════════════════════════════════════════════════════════
# USER AGENT POOL
# ═══════════════════════════════════════════════════════════════════════════════

class UserAgentPool:
    """مجموعة User Agents حقيقية"""
    
    AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    ]
    
    @classmethod
    def get_random(cls) -> str:
        return random.choice(cls.AGENTS)
    
    @classmethod
    def get_headers(cls, user_agent: str = None) -> Dict[str, str]:
        """Headers واقعية - ✅ FIXED: Removed Accept-Encoding compression"""
        ua = user_agent or cls.get_random()
        
        return {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED FETCHERS
# ═══════════════════════════════════════════════════════════════════════════════

class CurlCffiFetcher:
    """محرك curl_cffi - يحاكي بصمة Chrome الحقيقية"""
    
    def __init__(self):
        self.available = CURL_CFFI_AVAILABLE
        if not self.available:
            logger.warning("⚠️ curl_cffi not available")
    
    def fetch(self, url: str) -> Optional[str]:
        if not self.available:
            return None
        
        try:
            logger.info("🔥 Strategy: CURL_CFFI (TLS bypass)")
            
            time.sleep(random.uniform(*config.JITTER_RANGE))
            
            headers = UserAgentPool.get_headers()
            
            response = curl_requests.get(
                url,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT,
                impersonate="chrome110",
                allow_redirects=True
            )
            
            if response.status_code == 200:
                logger.info(f"✅ CURL_CFFI success: {len(response.text):,} bytes")
                return response.text
            else:
                logger.warning(f"⚠️ CURL_CFFI returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ CURL_CFFI failed: {type(e).__name__}: {e}")
            return None

class RequestsHtmlFetcher:
    """محرك requests-html - يشغل JavaScript بدون متصفح"""
    
    def __init__(self):
        self.available = REQUESTS_HTML_AVAILABLE
        if not self.available:
            logger.warning("⚠️ requests-html not available")
    
    def fetch(self, url: str) -> Optional[str]:
        if not self.available:
            return None
        
        try:
            logger.info("🌐 Strategy: REQUESTS_HTML (JS rendering)")
            
            time.sleep(random.uniform(*config.JITTER_RANGE))
            
            session = HTMLSession()
            
            headers = UserAgentPool.get_headers()
            response = session.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            
            try:
                response.html.render(timeout=20, sleep=2)
            except:
                logger.debug("JS rendering skipped")
            
            if response.status_code == 200:
                logger.info(f"✅ REQUESTS_HTML success: {len(response.text):,} bytes")
                session.close()
                return response.text
            else:
                logger.warning(f"⚠️ REQUESTS_HTML returned {response.status_code}")
                session.close()
                return None
                
        except Exception as e:
            logger.error(f"❌ REQUESTS_HTML failed: {type(e).__name__}: {e}")
            return None

class CloudScraperFetcher:
    """محرك cloudscraper - يتخطى Cloudflare"""
    
    def __init__(self):
        self.available = CLOUDSCRAPER_AVAILABLE
        if not self.available:
            logger.warning("⚠️ cloudscraper not available")
    
    def fetch(self, url: str) -> Optional[str]:
        if not self.available:
            return None
        
        try:
            logger.info("☁️  Strategy: CLOUDSCRAPER (Cloudflare bypass)")
            
            time.sleep(random.uniform(*config.JITTER_RANGE))
            
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
            
            headers = UserAgentPool.get_headers()
            response = scraper.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                logger.info(f"✅ CLOUDSCRAPER success: {len(response.text):,} bytes")
                return response.text
            else:
                logger.warning(f"⚠️ CLOUDSCRAPER returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ CLOUDSCRAPER failed: {type(e).__name__}: {e}")
            return None

class StandardRequestsFetcher:
    """محرك requests القياسي - fallback نهائي"""
    
    def fetch(self, url: str) -> Optional[str]:
        try:
            logger.info("📡 Strategy: STANDARD_REQUESTS (fallback)")
            
            time.sleep(random.uniform(*config.JITTER_RANGE))
            
            session = standard_requests.Session()
            headers = UserAgentPool.get_headers()
            
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=config.MAX_RETRIES,
                backoff_factor=config.RETRY_BACKOFF,
                status_forcelist=[403, 429, 500, 502, 503, 504],
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            response = session.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                logger.info(f"✅ STANDARD_REQUESTS success: {len(response.text):,} bytes")
                return response.text
            else:
                logger.warning(f"⚠️ STANDARD_REQUESTS returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ STANDARD_REQUESTS failed: {type(e).__name__}: {e}")
            return None

# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-LAYER CACHE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class CacheManager:
    """نظام تخزين متعدد المستويات"""
    
    def __init__(self, cache_file: str = config.CACHE_FILE):
        self.cache_file = Path(cache_file)
        self.layers = {
            'fresh': None,
            'recent': None,
            'emergency': None
        }
        self.timestamps = {
            'fresh': None,
            'recent': None,
            'emergency': None
        }
        self._load_from_disk()
    
    def _load_from_disk(self):
        """تحميل من الملف"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self.layers = data.get('layers', self.layers)
                    self.timestamps = data.get('timestamps', self.timestamps)
                    logger.info("✅ Multi-layer cache loaded from disk")
            except Exception as e:
                logger.error(f"❌ Cache load error: {e}")
    
    def _save_to_disk(self):
        """حفظ إلى الملف"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump({
                    'layers': self.layers,
                    'timestamps': self.timestamps
                }, f)
            logger.debug("💾 Cache saved to disk")
        except Exception as e:
            logger.error(f"❌ Cache save error: {e}")
    
    def get(self, layer: str = 'auto') -> Optional[str]:
        """الحصول على cache من طبقة محددة"""
        now = time.time()
        
        if layer == 'auto':
            for layer_name, max_age in [
                ('fresh', config.CACHE_DURATION),
                ('recent', config.LONG_CACHE_DURATION),
                ('emergency', config.EMERGENCY_CACHE_DURATION)
            ]:
                if self.layers[layer_name] and self.timestamps[layer_name]:
                    age = now - self.timestamps[layer_name]
                    if age <= max_age:
                        logger.info(f"📦 Cache hit: {layer_name} (age: {int(age)}s)")
                        return self.layers[layer_name]
            
            logger.debug("⏰ All cache layers expired")
            return None
        
        else:
            if self.layers[layer] and self.timestamps[layer]:
                age = now - self.timestamps[layer]
                logger.info(f"📦 Cache from {layer}: {int(age)}s old")
                return self.layers[layer]
            return None
    
    def set(self, xml: str):
        """حفظ في جميع الطبقات"""
        now = time.time()
        for layer in self.layers.keys():
            self.layers[layer] = xml
            self.timestamps[layer] = now
        
        self._save_to_disk()
        logger.info(f"💾 Cache updated in all layers")
    
    def get_emergency_fallback(self) -> Optional[str]:
        """الحصول على أي cache متاح (حالات الطوارئ)"""
        for layer in ['emergency', 'recent', 'fresh']:
            if self.layers[layer]:
                age = time.time() - self.timestamps[layer] if self.timestamps[layer] else 999999
                logger.warning(f"🚨 EMERGENCY fallback from {layer} (age: {int(age)}s)")
                return self.layers[layer]
        
        logger.critical("💥 NO CACHE AVAILABLE AT ALL")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI AI OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiOptimizer:
    """محسن المحتوى بالذكاء الاصطناعي"""
    
    def __init__(self):
        self.enabled = False
        self.model = None
        
        if not GENAI_AVAILABLE:
            logger.warning("⚠️ google-generativeai not installed")
            return
        
        if not config.GEMINI_API_KEY:
            logger.warning("⚠️ GEMINI_API_KEY not set")
            return
        
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            
            self.model = genai.GenerativeModel(config.GEMINI_MODEL)
            
            test = self.model.generate_content(
                "Hi",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=50,
                    temperature=0.7
                ),
                request_options={"timeout": 10}
            )
            
            if test and test.text:
                self.enabled = True
                logger.info(f"✅ Gemini AI active ({config.GEMINI_MODEL})")
            else:
                logger.warning("⚠️ Gemini test failed - no response")
                
        except Exception as e:
            logger.error(f"❌ Gemini initialization failed: {type(e).__name__}: {e}")
    
    def optimize_title(self, title: str) -> str:
        """تحسين العنوان"""
        if not self.enabled or not title:
            return title
        
        try:
            prompt = f'''Optimize this title for Reddit engagement (max 250 chars, catchy, 1-2 emoji):
"{title}"

Return ONLY the optimized title.'''
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=300,
                    temperature=0.8
                ),
                request_options={"timeout": 15}
            )
            
            optimized = response.text.strip().replace('**', '').replace('*', '')
            optimized = re.sub(r'\n+', ' ', optimized)[:250]
            
            logger.debug(f"AI Title: {optimized[:40]}...")
            return optimized
            
        except Exception as e:
            logger.error(f"❌ Title optimization failed: {e}")
            return title
    
    def generate_description(self, title: str, original_desc: str) -> str:
        """توليد وصف"""
        if not self.enabled:
            return original_desc[:300]
        
        try:
            prompt = f'''Create engaging Reddit description (2-3 sentences):
Title: "{title}"
Original: "{original_desc[:200]}"

Return ONLY the description.'''
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=400,
                    temperature=0.8
                ),
                request_options={"timeout": 15}
            )
            
            description = response.text.strip().replace('**', '').replace('*', '')
            logger.debug(f"AI Desc: {description[:40]}...")
            return description[:400]
            
        except Exception as e:
            logger.error(f"❌ Description generation failed: {e}")
            return original_desc[:300]

# ═══════════════════════════════════════════════════════════════════════════════
# RSS PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

class RSSProcessor:
    """معالج RSS بالاستراتيجيات المتعددة"""
    
    def __init__(self, optimizer: GeminiOptimizer, cache: CacheManager):
        self.optimizer = optimizer
        self.cache = cache
        
        self.fetchers = [
            ('CURL_CFFI', CurlCffiFetcher()),
            ('REQUESTS_HTML', RequestsHtmlFetcher()),
            ('CLOUDSCRAPER', CloudScraperFetcher()),
            ('STANDARD_REQUESTS', StandardRequestsFetcher()),
        ]
        
        logger.info("✅ RSS Processor initialized with all fetchers")
    
    def fetch_feed(self, force: bool = False) -> Optional[str]:
        """جلب RSS باستخدام جميع الاستراتيجيات"""
        
        if not force:
            cached = self.cache.get('auto')
            if cached:
                return cached
        
        urls_to_try = [config.ORIGINAL_RSS_URL] + config.FALLBACK_RSS_URLS
        
        for url in urls_to_try:
            logger.info(f"🎯 Trying URL: {url}")
            
            for fetcher_name, fetcher in self.fetchers:
                try:
                    xml = fetcher.fetch(url)
                    
                    if xml and self._validate_xml(xml):
                        logger.info(f"✅ SUCCESS with {fetcher_name}")
                        return xml
                    
                except Exception as e:
                    logger.error(f"❌ {fetcher_name} exception: {e}")
                
                time.sleep(1.5)
        
        logger.error("❌ ALL FETCHING STRATEGIES FAILED")
        return self.cache.get_emergency_fallback()
    
    def _validate_xml(self, xml: str) -> bool:
        """التحقق من صلاحية XML"""
        try:
            if len(xml.strip()) < 100:
                logger.warning("⚠️ XML too short")
                return False
            
            if '<e>' in xml and 'Unavailable' in xml:
                logger.warning("⚠️ Error response detected")
                return False
            
            root = ET.fromstring(xml)
            items = root.findall('.//item')
            
            if len(items) == 0:
                logger.warning("⚠️ No items in XML")
                return False
            
            logger.info(f"✅ Valid XML with {len(items)} items")
            return True
            
        except ET.ParseError as e:
            logger.error(f"❌ XML parse error: {e}")
            return False
    
    def parse_items(self, xml: str) -> List[Dict]:
        """تحليل عناصر RSS"""
        try:
            root = ET.fromstring(xml)
            items = []
            
            for item in root.findall('.//item'):
                title = item.find('title')
                link = item.find('link')
                desc = item.find('description')
                date = item.find('pubDate')
                
                if title is not None and link is not None:
                    desc_text = ""
                    if desc is not None and desc.text:
                        desc_text = re.sub(r'<[^>]+>', '', desc.text).strip()
                    
                    items.append({
                        'title': title.text or "Untitled",
                        'link': link.text or "",
                        'description': desc_text or "No description",
                        'pubDate': date.text if date is not None else datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
                    })
            
            logger.info(f"✅ Parsed {len(items)} items")
            return items[:config.MAX_FEED_ITEMS]
            
        except Exception as e:
            logger.error(f"❌ Parse failed: {e}")
            return []
    
    def create_dynamic_link(self, link: str, post_id: str) -> str:
        """إنشاء رابط ديناميكي"""
        timestamp = int(time.time())
        token = hashlib.md5(f"{post_id}{timestamp}".encode()).hexdigest()[:8]
        
        params = urlencode({
            'source': 'reddit',
            'utm_campaign': 'rss_auto',
            'utm_medium': 'social',
            'post_id': post_id,
            'ref': token,
            't': timestamp
        })
        
        separator = '&' if '?' in link else '?'
        return f"{link}{separator}{params}"
    
    def optimize_item(self, item: Dict, index: int) -> Dict:
        """تحسين عنصر واحد"""
        post_id = hashlib.md5(item['link'].encode()).hexdigest()[:12]
        
        opt_title = self.optimizer.optimize_title(item['title'])
        opt_desc = self.optimizer.generate_description(opt_title, item['description'])
        dyn_link = self.create_dynamic_link(item['link'], post_id)
        
        logger.info(f"✅ Optimized item {index + 1}: {opt_title[:35]}...")
        
        return {
            'title': opt_title,
            'link': dyn_link,
            'description': opt_desc,
            'pubDate': item['pubDate'],
            'guid': post_id
        }
    
    def generate_xml(self, items: List[Dict]) -> str:
        """توليد RSS XML"""
        rss = ET.Element('rss', {
            'version': '2.0',
            'xmlns:atom': 'http://www.w3.org/2005/Atom'
        })
        
        channel = ET.SubElement(rss, 'channel')
        
        ET.SubElement(channel, 'title').text = config.FEED_TITLE
        ET.SubElement(channel, 'link').text = config.FEED_LINK
        ET.SubElement(channel, 'description').text = config.FEED_DESCRIPTION
        ET.SubElement(channel, 'language').text = config.FEED_LANGUAGE
        ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        ET.SubElement(channel, 'generator').text = f"{config.APP_NAME} v{config.VERSION}"
        
        for item_data in items:
            item = ET.SubElement(channel, 'item')
            ET.SubElement(item, 'title').text = item_data['title']
            ET.SubElement(item, 'link').text = item_data['link']
            ET.SubElement(item, 'description').text = item_data['description']
            ET.SubElement(item, 'pubDate').text = item_data['pubDate']
            ET.SubElement(item, 'guid', {'isPermaLink': 'false'}).text = item_data['guid']
        
        xml = ET.tostring(rss, encoding='unicode', method='xml')
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml}'
    
    def get_feed(self, force: bool = False) -> Optional[str]:
        """الحصول على RSS feed كامل"""
        
        xml = self.fetch_feed(force=force)
        if not xml:
            logger.error("❌ Failed to fetch feed")
            return None
        
        items = self.parse_items(xml)
        if not items:
            logger.error("❌ No items parsed")
            return None
        
        optimized = []
        for i, item in enumerate(items):
            try:
                optimized.append(self.optimize_item(item, i))
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"❌ Failed to optimize item {i}: {e}")
        
        if not optimized:
            logger.error("❌ No items optimized")
            return None
        
        feed_xml = self.generate_xml(optimized)
        
        self.cache.set(feed_xml)
        
        logger.info(f"✅ Feed generated: {len(optimized)} items")
        return feed_xml

# ═══════════════════════════════════════════════════════════════════════════════
# FLASK APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

cache_manager = CacheManager()
optimizer = GeminiOptimizer()
processor = RSSProcessor(optimizer, cache_manager)
start_time = time.time()

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    base_url = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{config.FLASK_PORT}')
    
    cache_ages = {}
    for layer in ['fresh', 'recent', 'emergency']:
        if cache_manager.timestamps[layer]:
            cache_ages[layer] = int(time.time() - cache_manager.timestamps[layer])
    
    return jsonify({
        "status": "operational",
        "version": config.VERSION,
        "uptime": f"{hours}h {minutes}m",
        "feed_url": f"{base_url}/feed",
        "endpoints": {
            "feed": "/feed",
            "health": "/health",
            "refresh": "/refresh (POST)",
            "stats": "/stats"
        },
        "features": {
            "ai_optimization": optimizer.enabled,
            "curl_cffi": CURL_CFFI_AVAILABLE,
            "requests_html": REQUESTS_HTML_AVAILABLE,
            "cloudscraper": CLOUDSCRAPER_AVAILABLE,
        },
        "cache": {
            "layers": cache_ages
        }
    })

@app.route('/health')
def health():
    """فحص الصحة"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ai": optimizer.enabled,
        "cache_valid": cache_manager.get('auto') is not None
    })

@app.route('/feed')
def feed():
    """نقطة نهاية RSS"""
    try:
        logger.info(f"📡 Feed request from {request.remote_addr}")
        
        xml = processor.get_feed()
        
        if not xml:
            logger.error("❌ Feed generation failed")
            return Response(
                '<?xml version="1.0"?><error>Feed temporarily unavailable</error>',
                mimetype='application/xml',
                status=503
            )
        
        return Response(
            xml,
            mimetype='application/xml',
            headers={
                'Cache-Control': f'public, max-age={config.CACHE_DURATION}',
                'X-RSS-Version': config.VERSION,
                'X-Generator': config.APP_NAME
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Feed endpoint error: {e}")
        import traceback
        traceback.print_exc()
        
        return Response(
            f'<?xml version="1.0"?><error>{str(e)}</error>',
            mimetype='application/xml',
            status=500
        )

@app.route('/refresh', methods=['POST'])
def refresh():
    """تحديث يدوي"""
    try:
        logger.info("🔄 Manual refresh requested")
        xml = processor.get_feed(force=True)
        
        items_count = xml.count('<item>') if xml else 0
        
        return jsonify({
            "success": bool(xml),
            "items": items_count,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Refresh error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/stats')
def stats():
    """إحصائيات"""
    return jsonify({
        "system": {
            "version": config.VERSION,
            "uptime_seconds": int(time.time() - start_time),
            "python_version": sys.version
        },
        "capabilities": {
            "ai": optimizer.enabled,
            "curl_cffi": CURL_CFFI_AVAILABLE,
            "requests_html": REQUESTS_HTML_AVAILABLE,
            "cloudscraper": CLOUDSCRAPER_AVAILABLE,
            "bs4": BS4_AVAILABLE
        },
        "cache": {
            "layers": {
                layer: {
                    "age": int(time.time() - cache_manager.timestamps[layer]) if cache_manager.timestamps[layer] else None,
                    "has_data": cache_manager.layers[layer] is not None
                }
                for layer in ['fresh', 'recent', 'emergency']
            }
        }
    })

# ═══════════════════════════════════════════════════════════════════════════════
# SELF-PING
# ═══════════════════════════════════════════════════════════════════════════════

class SelfPing:
    """نظام ping ذاتي"""
    
    def __init__(self):
        self.url = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{config.FLASK_PORT}')
        
        if config.SELF_PING_ENABLED:
            import threading
            self.thread = threading.Thread(target=self._ping_loop, daemon=True)
            self.thread.start()
            logger.info(f"💓 Self-ping started (interval: {config.SELF_PING_INTERVAL}s)")
    
    def _ping_loop(self):
        """حلقة ping"""
        while True:
            time.sleep(config.SELF_PING_INTERVAL)
            try:
                response = standard_requests.get(f"{self.url}/health", timeout=10)
                if response.status_code == 200:
                    logger.debug("✅ Self-ping successful")
                else:
                    logger.warning(f"⚠️ Self-ping returned {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Self-ping failed: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """نقطة الدخول"""
    try:
        logger.info("=" * 80)
        logger.info(f"🚀 {config.APP_NAME} v{config.VERSION}")
        logger.info("=" * 80)
        
        logger.info(f"🤖 AI Optimization: {'✅ Active' if optimizer.enabled else '❌ Disabled'}")
        logger.info(f"🔥 curl_cffi (TLS bypass): {'✅ Available' if CURL_CFFI_AVAILABLE else '❌ Not installed'}")
        logger.info(f"🌐 requests-html: {'✅ Available' if REQUESTS_HTML_AVAILABLE else '❌ Not installed'}")
        logger.info(f"☁️  cloudscraper: {'✅ Available' if CLOUDSCRAPER_AVAILABLE else '❌ Not installed'}")
        logger.info(f"📡 Direct RSS Source: {config.ORIGINAL_RSS_URL}")
        logger.info(f"💾 Multi-layer cache: 5m / 24h / 7d")
        logger.info("=" * 80)
        
        SelfPing()
        
        # ✅ FIXED: Removed pre-fetch to allow fast port binding
        # processor.get_feed(force=True)
        
        logger.info("=" * 80)
        logger.info(f"🌐 Starting Waitress on {config.FLASK_HOST}:{config.FLASK_PORT}")
        logger.info("✅ SYSTEM OPERATIONAL - Port bound immediately")
        
        base_url = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{config.FLASK_PORT}')
        logger.info(f"📡 Feed URL: {base_url}/feed")
        logger.info("=" * 80)
        
        serve(
            app,
            host=config.FLASK_HOST,
            port=config.FLASK_PORT,
            threads=8,
            channel_timeout=120,
            _quiet=False
        )
        
    except KeyboardInterrupt:
        logger.info("\n⏹️  Shutting down...")
        sys.exit(0)
        
    except Exception as e:
        logger.critical(f"💥 Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
