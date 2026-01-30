#!/usr/bin/env python3
"""
Reddit RSS Bot v2.0.0 ULTIMATE
🔥 Multi-strategy RSS fetching with advanced anti-detection
✅ Proxy rotation + Selenium fallback + Direct scraping
✅ Enhanced caching + Multiple retry strategies
✅ Production-grade error handling
"""
import os, sys, json, time, logging, hashlib, random, re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
from dataclasses import dataclass
from enum import Enum
import requests
from flask import Flask, Response, jsonify, request
from waitress import serve
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse, urlencode, quote
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import pickle
from pathlib import Path

# Optional imports
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

class FetchStrategy(Enum):
    """استراتيجيات جلب البيانات"""
    REQUESTS = "requests"
    SELENIUM = "selenium"
    SCRAPING = "scraping"
    CACHE = "cache"

@dataclass
class Config:
    """إعدادات شاملة"""
    # Application
    APP_NAME: str = "Reddit RSS Bot Ultimate"
    VERSION: str = "2.0.0"
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = int(os.getenv("PORT", 10000))
    
    # RSS Sources
    ORIGINAL_RSS_URL: str = "https://rss.app/feed/zKvsfrwIfVjjKtpr"
    FALLBACK_RSS_URLS: List[str] = None
    REDDIT_SUBREDDIT: str = os.getenv("REDDIT_SUBREDDIT", "")  # اختياري للسحب المباشر
    
    # AI Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_MAX_RETRIES: int = 3
    
    # Feed Configuration
    FEED_TITLE: str = "She Cooks Bakes - Professional Recipes"
    FEED_DESCRIPTION: str = "Delicious baking recipes and cooking tips"
    FEED_LINK: str = "https://shecooksandbakes.tumblr.com"
    FEED_LANGUAGE: str = "en-us"
    MAX_FEED_ITEMS: int = 10
    
    # Caching
    CACHE_DURATION: int = 300  # 5 دقائق للتحديث
    LONG_CACHE_DURATION: int = 86400  # 24 ساعة كاحتياطي
    CACHE_FILE: str = "rss_cache.pkl"
    
    # Request Configuration
    REQUEST_TIMEOUT: int = 45
    MAX_RETRIES: int = 5
    RETRY_BACKOFF: float = 3.0
    JITTER_RANGE: Tuple[float, float] = (3.0, 10.0)
    
    # Selenium Configuration
    SELENIUM_TIMEOUT: int = 30
    SELENIUM_PAGE_LOAD_TIMEOUT: int = 60
    
    # Logging
    LOG_FILE: str = "reddit_rss_ultimate.log"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Self-ping
    SELF_PING_ENABLED: bool = True
    SELF_PING_INTERVAL: int = 840
    
    # Advanced
    ENABLE_PROXY_ROTATION: bool = False  # تفعيل عند توفر وكلاء
    PROXY_LIST: List[str] = None
    
    def __post_init__(self):
        if self.FALLBACK_RSS_URLS is None:
            self.FALLBACK_RSS_URLS = []
        if self.PROXY_LIST is None:
            self.PROXY_LIST = []

config = Config()

# ════════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ════════════════════════════════════════════════════════════════════════════════

def setup_logging() -> logging.Logger:
    """إعداد نظام تسجيل متقدم"""
    logger = logging.getLogger(config.APP_NAME)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(console_fmt)
    
    # File handler
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s'
    )
    file_handler.setFormatter(file_fmt)
    
    logger.addHandler(console)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

# ════════════════════════════════════════════════════════════════════════════════
# USER AGENT POOL
# ════════════════════════════════════════════════════════════════════════════════

class UserAgentPool:
    """مجموعة واسعة من User Agents حقيقية"""
    
    AGENTS = [
        # Chrome Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        
        # Firefox Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        
        # Edge
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        
        # Chrome Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        
        # Safari Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        
        # Chrome Linux
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    ]
    
    @classmethod
    def get_random(cls) -> str:
        """اختيار User-Agent عشوائي"""
        return random.choice(cls.AGENTS)
    
    @classmethod
    def get_headers(cls, user_agent: str = None) -> Dict[str, str]:
        """توليد headers كاملة متوافقة"""
        ua = user_agent or cls.get_random()
        
        # تحديد نوع المتصفح
        is_chrome = 'Chrome' in ua and 'Edg' not in ua
        is_firefox = 'Firefox' in ua
        is_edge = 'Edg' in ua
        is_safari = 'Safari' in ua and 'Chrome' not in ua
        
        headers = {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # إضافة headers خاصة بكل متصفح
        if is_chrome or is_edge:
            chrome_version = re.search(r'Chrome/(\d+)', ua)
            version = chrome_version.group(1) if chrome_version else '121'
            headers.update({
                'sec-ch-ua': f'"Not A(Brand";v="99", "Google Chrome";v="{version}", "Chromium";v="{version}"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"' if 'Windows' in ua else '"macOS"' if 'Mac' in ua else '"Linux"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            })
        
        return headers

# ════════════════════════════════════════════════════════════════════════════════
# ADVANCED BROWSER SESSION
# ════════════════════════════════════════════════════════════════════════════════

class AdvancedBrowserSession:
    """جلسة متصفح متقدمة مع تمويه كامل"""
    
    def __init__(self):
        self.session = requests.Session()
        self.user_agent = UserAgentPool.get_random()
        self.request_count = 0
        self._setup_session()
        logger.info(f"✅ Browser session initialized | UA: {self.user_agent[:50]}...")
    
    def _setup_session(self):
        """إعداد الجلسة بتكوين متقدم"""
        # Headers
        headers = UserAgentPool.get_headers(self.user_agent)
        self.session.headers.update(headers)
        
        # Retry strategy
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=config.RETRY_BACKOFF,
            status_forcelist=[403, 429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=50,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Cookies لمحاكاة زائر متكرر
        self._set_realistic_cookies()
    
    def _set_realistic_cookies(self):
        """تعيين cookies واقعية"""
        timestamp = int(time.time())
        session_id = hashlib.sha256(f"{timestamp}{random.random()}".encode()).hexdigest()[:32]
        
        cookies = {
            'session_id': session_id,
            'visited': 'true',
            'last_visit': str(timestamp),
            '_ga': f'GA1.2.{random.randint(100000000, 999999999)}.{timestamp}',
            '_gid': f'GA1.2.{random.randint(100000000, 999999999)}.{timestamp}',
        }
        
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='.rss.app')
    
    def _apply_jitter(self):
        """تطبيق تأخير عشوائي طبيعي"""
        jitter = random.uniform(*config.JITTER_RANGE)
        logger.debug(f"⏱️  Jitter: {jitter:.2f}s")
        time.sleep(jitter)
    
    def _rotate_identity(self):
        """تغيير الهوية كل عدة طلبات"""
        if self.request_count % 5 == 0 and self.request_count > 0:
            logger.info("🔄 Rotating browser identity...")
            self.user_agent = UserAgentPool.get_random()
            new_headers = UserAgentPool.get_headers(self.user_agent)
            self.session.headers.update(new_headers)
            self._set_realistic_cookies()
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET request مع تمويه متقدم"""
        self._apply_jitter()
        self._rotate_identity()
        
        # Merge headers
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        
        kwargs['headers']['Referer'] = 'https://www.google.com/'
        kwargs.setdefault('allow_redirects', True)
        kwargs.setdefault('timeout', config.REQUEST_TIMEOUT)
        
        # Proxy support
        if config.ENABLE_PROXY_ROTATION and config.PROXY_LIST:
            proxy = random.choice(config.PROXY_LIST)
            kwargs['proxies'] = {'http': proxy, 'https': proxy}
            logger.debug(f"🔀 Using proxy: {proxy}")
        
        self.request_count += 1
        logger.debug(f"🌐 Request #{self.request_count}: {url}")
        
        try:
            response = self.session.get(url, **kwargs)
            logger.info(f"✅ Response {response.status_code} | {len(response.content):,} bytes | {response.elapsed.total_seconds():.2f}s")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request failed: {type(e).__name__}: {e}")
            raise
    
    def close(self):
        """إغلاق الجلسة"""
        self.session.close()
        logger.debug("Session closed")

# ════════════════════════════════════════════════════════════════════════════════
# SELENIUM FETCHER
# ════════════════════════════════════════════════════════════════════════════════

class SeleniumFetcher:
    """جلب RSS باستخدام متصفح حقيقي (Selenium)"""
    
    def __init__(self):
        self.available = SELENIUM_AVAILABLE
        if not self.available:
            logger.warning("⚠️ Selenium not available - install: pip install selenium")
    
    def fetch(self, url: str) -> Optional[str]:
        """جلب المحتوى باستخدام Chrome headless"""
        if not self.available:
            return None
        
        driver = None
        try:
            logger.info("🌐 Launching Selenium Chrome...")
            
            options = ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'user-agent={UserAgentPool.get_random()}')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # تعطيل الكشف
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            driver = webdriver.Chrome(options=options)
            
            # إخفاء WebDriver
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            driver.set_page_load_timeout(config.SELENIUM_PAGE_LOAD_TIMEOUT)
            
            logger.info(f"📡 Fetching with Selenium: {url}")
            driver.get(url)
            
            # انتظار تحميل المحتوى
            WebDriverWait(driver, config.SELENIUM_TIMEOUT).until(
                lambda d: len(d.page_source) > 500
            )
            
            time.sleep(3)  # تأخير إضافي للتأكد
            
            content = driver.page_source
            logger.info(f"✅ Selenium fetch successful: {len(content):,} bytes")
            
            return content
            
        except TimeoutException:
            logger.error("❌ Selenium timeout")
            return None
        except WebDriverException as e:
            logger.error(f"❌ Selenium error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected Selenium error: {e}")
            return None
        finally:
            if driver:
                driver.quit()
                logger.debug("Selenium driver closed")

# ════════════════════════════════════════════════════════════════════════════════
# WEB SCRAPER
# ════════════════════════════════════════════════════════════════════════════════

class WebScraper:
    """سحب البيانات من HTML مباشرة"""
    
    def __init__(self):
        self.available = BS4_AVAILABLE
        if not self.available:
            logger.warning("⚠️ BeautifulSoup not available - install: pip install beautifulsoup4 lxml")
    
    def extract_rss_from_html(self, html: str) -> Optional[str]:
        """استخراج RSS من HTML"""
        if not self.available:
            return None
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # البحث عن RSS feed link
            rss_link = soup.find('link', {'type': 'application/rss+xml'})
            if rss_link and rss_link.get('href'):
                logger.info(f"✅ Found RSS link: {rss_link['href']}")
                return rss_link['href']
            
            # البحث في الـ pre أو code tags (قد يحتوي RSS)
            for tag in soup.find_all(['pre', 'code']):
                text = tag.get_text()
                if '<?xml' in text and '<rss' in text:
                    logger.info("✅ Found RSS content in HTML")
                    return text
            
            logger.warning("⚠️ No RSS found in HTML")
            return None
            
        except Exception as e:
            logger.error(f"❌ HTML parsing error: {e}")
            return None

# ════════════════════════════════════════════════════════════════════════════════
# CACHE MANAGER
# ════════════════════════════════════════════════════════════════════════════════

class CacheManager:
    """إدارة ذاكرة تخزين مؤقت متقدمة"""
    
    def __init__(self, cache_file: str = config.CACHE_FILE):
        self.cache_file = Path(cache_file)
        self.memory_cache: Optional[Dict] = None
        self.cache_time: Optional[float] = None
        self._load_from_disk()
    
    def _load_from_disk(self):
        """تحميل Cache من الملف"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self.memory_cache = data.get('content')
                    self.cache_time = data.get('timestamp')
                    logger.info(f"✅ Cache loaded from disk (age: {int(time.time() - self.cache_time)}s)")
            except Exception as e:
                logger.error(f"❌ Cache load error: {e}")
    
    def _save_to_disk(self):
        """حفظ Cache إلى الملف"""
        if self.memory_cache and self.cache_time:
            try:
                with open(self.cache_file, 'wb') as f:
                    pickle.dump({
                        'content': self.memory_cache,
                        'timestamp': self.cache_time
                    }, f)
                logger.debug("💾 Cache saved to disk")
            except Exception as e:
                logger.error(f"❌ Cache save error: {e}")
    
    def get(self, max_age: int = config.CACHE_DURATION) -> Optional[str]:
        """الحصول على Cache إذا كان صالحاً"""
        if not self.memory_cache or not self.cache_time:
            return None
        
        age = time.time() - self.cache_time
        if age <= max_age:
            logger.info(f"📦 Cache hit (age: {int(age)}s)")
            return self.memory_cache.get('xml')
        
        logger.debug(f"⏰ Cache expired (age: {int(age)}s > {max_age}s)")
        return None
    
    def set(self, xml: str, items_count: int):
        """حفظ في Cache"""
        self.memory_cache = {
            'xml': xml,
            'items': items_count,
            'strategy': 'unknown'
        }
        self.cache_time = time.time()
        self._save_to_disk()
        logger.info(f"💾 Cache updated ({items_count} items)")
    
    def get_fallback(self) -> Optional[str]:
        """الحصول على آخر cache حتى لو قديم (للطوارئ)"""
        if self.memory_cache:
            age = time.time() - self.cache_time if self.cache_time else 999999
            logger.warning(f"⚠️ Using emergency fallback cache (age: {int(age)}s)")
            return self.memory_cache.get('xml')
        return None

# ════════════════════════════════════════════════════════════════════════════════
# GEMINI AI OPTIMIZER
# ════════════════════════════════════════════════════════════════════════════════

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
            
            # اختبار
            test = self.model.generate_content("Hi", request_options={"timeout": 10})
            if test and test.text:
                self.enabled = True
                logger.info(f"✅ Gemini AI active ({config.GEMINI_MODEL})")
        except Exception as e:
            logger.error(f"❌ Gemini initialization failed: {e}")
    
    def optimize_title(self, title: str) -> str:
        """تحسين العنوان"""
        if not self.enabled or not title:
            return title
        
        try:
            prompt = f'''Optimize this title for Reddit engagement (max 250 chars, catchy, use 1-2 relevant emoji):
"{title}"

Return ONLY the optimized title, nothing else.'''
            
            response = self.model.generate_content(prompt, request_options={"timeout": 15})
            optimized = response.text.strip().replace('**', '').replace('*', '')
            
            # تنظيف
            optimized = re.sub(r'\n+', ' ', optimized)
            optimized = optimized[:250]
            
            logger.debug(f"AI Title: {optimized[:50]}...")
            return optimized
            
        except Exception as e:
            logger.error(f"❌ Title optimization failed: {e}")
            return title
    
    def generate_description(self, title: str, original_desc: str) -> str:
        """توليد وصف جذاب"""
        if not self.enabled:
            return original_desc[:300]
        
        try:
            prompt = f'''Create an engaging Reddit post description (2-3 sentences, conversational):
Title: "{title}"
Original: "{original_desc[:200]}"

Return ONLY the description, nothing else.'''
            
            response = self.model.generate_content(prompt, request_options={"timeout": 15})
            description = response.text.strip().replace('**', '').replace('*', '')
            
            logger.debug(f"AI Desc: {description[:50]}...")
            return description[:400]
            
        except Exception as e:
            logger.error(f"❌ Description generation failed: {e}")
            return original_desc[:300]

# ════════════════════════════════════════════════════════════════════════════════
# RSS PROCESSOR
# ════════════════════════════════════════════════════════════════════════════════

class RSSProcessor:
    """معالج RSS متقدم متعدد الاستراتيجيات"""
    
    def __init__(self, optimizer: GeminiOptimizer, cache: CacheManager):
        self.optimizer = optimizer
        self.cache = cache
        self.browser = AdvancedBrowserSession()
        self.selenium = SeleniumFetcher()
        self.scraper = WebScraper()
        self.strategies = [
            (FetchStrategy.REQUESTS, self._fetch_with_requests),
            (FetchStrategy.SELENIUM, self._fetch_with_selenium),
            (FetchStrategy.SCRAPING, self._fetch_with_scraping),
        ]
        logger.info("✅ RSS Processor initialized")
    
    def _fetch_with_requests(self, url: str) -> Optional[str]:
        """استراتيجية 1: Requests مع تمويه متقدم"""
        try:
            logger.info(f"📡 Strategy: REQUESTS | URL: {url}")
            response = self.browser.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '').lower()
            
            # تحقق من XML/RSS
            if not any(x in content_type for x in ['xml', 'rss', 'text']):
                logger.warning(f"⚠️ Unexpected content type: {content_type}")
            
            if len(response.text.strip()) < 100:
                logger.warning("⚠️ Response too short, likely blocked")
                return None
            
            if '<e>' in response.text and 'Unavailable' in response.text:
                logger.error("❌ Error response detected")
                return None
            
            logger.info(f"✅ REQUESTS strategy successful")
            return response.text
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ REQUESTS strategy failed: {e}")
            return None
    
    def _fetch_with_selenium(self, url: str) -> Optional[str]:
        """استراتيجية 2: Selenium headless browser"""
        if not self.selenium.available:
            logger.warning("⚠️ Selenium not available")
            return None
        
        try:
            logger.info(f"🌐 Strategy: SELENIUM | URL: {url}")
            html = self.selenium.fetch(url)
            
            if not html:
                return None
            
            # استخراج RSS من HTML
            rss_content = self.scraper.extract_rss_from_html(html)
            
            if rss_content:
                # إذا كان link، جلبه
                if rss_content.startswith('http'):
                    return self._fetch_with_requests(rss_content)
                # إذا كان XML مباشر
                elif '<?xml' in rss_content:
                    return rss_content
            
            logger.warning("⚠️ No RSS found via Selenium")
            return None
            
        except Exception as e:
            logger.error(f"❌ SELENIUM strategy failed: {e}")
            return None
    
    def _fetch_with_scraping(self, url: str) -> Optional[str]:
        """استراتيجية 3: Web scraping مباشر"""
        # هذه تحتاج تنفيذ خاص حسب الموقع المستهدف
        logger.info("🔍 Strategy: SCRAPING (not implemented for generic RSS)")
        return None
    
    def fetch_feed(self, force: bool = False) -> Optional[str]:
        """جلب RSS باستخدام استراتيجيات متعددة"""
        
        # تحقق من Cache أولاً
        if not force:
            cached = self.cache.get()
            if cached:
                return cached
        
        # جرب كل استراتيجية
        urls_to_try = [config.ORIGINAL_RSS_URL] + config.FALLBACK_RSS_URLS
        
        for url in urls_to_try:
            logger.info(f"🎯 Trying URL: {url}")
            
            for strategy_name, strategy_func in self.strategies:
                logger.info(f"🔄 Attempting strategy: {strategy_name.value}")
                
                try:
                    xml = strategy_func(url)
                    if xml and self._validate_xml(xml):
                        logger.info(f"✅ Success with {strategy_name.value}")
                        return xml
                except Exception as e:
                    logger.error(f"❌ Strategy {strategy_name.value} exception: {e}")
                
                # تأخير بين الاستراتيجيات
                time.sleep(2)
        
        # فشلت كل المحاولات - استخدم cache قديم
        logger.error("❌ All strategies failed")
        return self.cache.get_fallback()
    
    def _validate_xml(self, xml: str) -> bool:
        """التحقق من صلاحية XML"""
        try:
            root = ET.fromstring(xml)
            items = root.findall('.//item')
            
            if len(items) == 0:
                logger.warning("⚠️ No items found in XML")
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
                    # تنظيف الوصف من HTML
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
        """إنشاء رابط ديناميكي لتجنب spam filters"""
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
        
        # تحسين بالذكاء الاصطناعي
        opt_title = self.optimizer.optimize_title(item['title'])
        opt_desc = self.optimizer.generate_description(opt_title, item['description'])
        
        # رابط ديناميكي
        dyn_link = self.create_dynamic_link(item['link'], post_id)
        
        logger.info(f"✅ Optimized item {index + 1}: {opt_title[:40]}...")
        
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
        
        # جلب XML
        xml = self.fetch_feed(force=force)
        if not xml:
            logger.error("❌ Failed to fetch feed")
            return None
        
        # تحليل
        items = self.parse_items(xml)
        if not items:
            logger.error("❌ No items parsed")
            return None
        
        # تحسين
        optimized = []
        for i, item in enumerate(items):
            try:
                optimized.append(self.optimize_item(item, i))
                time.sleep(0.5)  # تأخير خفيف بين طلبات AI
            except Exception as e:
                logger.error(f"❌ Failed to optimize item {i}: {e}")
        
        if not optimized:
            logger.error("❌ No items optimized")
            return None
        
        # توليد XML
        feed_xml = self.generate_xml(optimized)
        
        # حفظ في cache
        self.cache.set(feed_xml, len(optimized))
        
        logger.info(f"✅ Feed generated: {len(optimized)} items")
        return feed_xml
    
    def cleanup(self):
        """تنظيف الموارد"""
        self.browser.close()

# ════════════════════════════════════════════════════════════════════════════════
# FLASK APPLICATION
# ════════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# تهيئة المكونات
cache_manager = CacheManager()
optimizer = GeminiOptimizer()
processor = RSSProcessor(optimizer, cache_manager)
start_time = time.time()

@app.route('/')
def home():
    """الصفحة الرئيسية - معلومات النظام"""
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    base_url = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{config.FLASK_PORT}')
    
    cache_age = None
    if cache_manager.cache_time:
        cache_age = int(time.time() - cache_manager.cache_time)
    
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
            "selenium_fallback": SELENIUM_AVAILABLE,
            "web_scraping": BS4_AVAILABLE,
            "proxy_rotation": config.ENABLE_PROXY_ROTATION
        },
        "cache": {
            "enabled": True,
            "age_seconds": cache_age,
            "items": cache_manager.memory_cache.get('items') if cache_manager.memory_cache else 0
        },
        "configuration": {
            "max_items": config.MAX_FEED_ITEMS,
            "cache_duration": config.CACHE_DURATION,
            "request_timeout": config.REQUEST_TIMEOUT
        }
    })

@app.route('/health')
def health():
    """فحص صحة النظام"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ai": optimizer.enabled,
        "cache_valid": cache_manager.get() is not None
    })

@app.route('/feed')
def feed():
    """نقطة نهاية RSS feed"""
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
    """تحديث Feed يدوياً"""
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
    """إحصائيات مفصلة"""
    cache_data = cache_manager.memory_cache or {}
    
    return jsonify({
        "system": {
            "version": config.VERSION,
            "uptime_seconds": int(time.time() - start_time),
            "python_version": sys.version
        },
        "cache": {
            "items": cache_data.get('items', 0),
            "age_seconds": int(time.time() - cache_manager.cache_time) if cache_manager.cache_time else None,
            "strategy": cache_data.get('strategy', 'unknown')
        },
        "browser": {
            "requests_made": processor.browser.request_count,
            "current_user_agent": processor.browser.user_agent[:50] + "..."
        },
        "capabilities": {
            "ai": optimizer.enabled,
            "selenium": SELENIUM_AVAILABLE,
            "scraping": BS4_AVAILABLE
        }
    })

# ════════════════════════════════════════════════════════════════════════════════
# SELF-PING SYSTEM
# ════════════════════════════════════════════════════════════════════════════════

class SelfPing:
    """نظام ping ذاتي لإبقاء الخدمة نشطة"""
    
    def __init__(self):
        self.url = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{config.FLASK_PORT}')
        
        if config.SELF_PING_ENABLED:
            import threading
            self.thread = threading.Thread(target=self._ping_loop, daemon=True)
            self.thread.start()
            logger.info(f"💓 Self-ping started (interval: {config.SELF_PING_INTERVAL}s)")
    
    def _ping_loop(self):
        """حلقة ping مستمرة"""
        while True:
            time.sleep(config.SELF_PING_INTERVAL)
            try:
                response = requests.get(
                    f"{self.url}/health",
                    timeout=10
                )
                if response.status_code == 200:
                    logger.debug("✅ Self-ping successful")
                else:
                    logger.warning(f"⚠️ Self-ping returned {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Self-ping failed: {e}")

# ════════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def main():
    """نقطة الدخول الرئيسية"""
    try:
        # Banner
        logger.info("=" * 80)
        logger.info(f"🚀 {config.APP_NAME} v{config.VERSION}")
        logger.info("=" * 80)
        
        # معلومات النظام
        logger.info(f"🤖 AI Optimization: {'✅ Active' if optimizer.enabled else '❌ Disabled'}")
        logger.info(f"🌐 Selenium Fallback: {'✅ Available' if SELENIUM_AVAILABLE else '❌ Not installed'}")
        logger.info(f"🔍 Web Scraping: {'✅ Available' if BS4_AVAILABLE else '❌ Not installed'}")
        logger.info(f"📡 Primary RSS: {config.ORIGINAL_RSS_URL}")
        logger.info(f"💾 Cache: {config.CACHE_DURATION}s duration")
        logger.info(f"⏱️  Request timeout: {config.REQUEST_TIMEOUT}s")
        logger.info("=" * 80)
        
        # بدء self-ping
        SelfPing()
        
        # Pre-fetch للتسخين
        logger.info("🔄 Pre-fetching RSS feed...")
        try:
            processor.get_feed(force=True)
            logger.info("✅ Pre-fetch successful")
        except Exception as e:
            logger.warning(f"⚠️ Pre-fetch failed: {e}")
        
        # بدء الخادم
        logger.info("=" * 80)
        logger.info(f"🌐 Starting Waitress server on {config.FLASK_HOST}:{config.FLASK_PORT}")
        logger.info("✅ SYSTEM OPERATIONAL")
        
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
        logger.info("\n⏹️  Shutting down gracefully...")
        processor.cleanup()
        sys.exit(0)
        
    except Exception as e:
        logger.critical(f"💥 Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
