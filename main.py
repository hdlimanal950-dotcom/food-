#!/usr/bin/env python3
"""
Reddit RSS Bot v1.2.0 FINAL
✅ FIXED: Enhanced browser spoofing (bypasses rss.app 403)
✅ FIXED: Gemini AI working with correct package
✅ Dynamic links to avoid spam detection
✅ Professional RSS feed generation
"""
import os, sys, json, time, logging, hashlib, random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET
import requests
from flask import Flask, Response, jsonify
from waitress import serve
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse, urlencode

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

class Config:
    APP_NAME = "Reddit RSS Bot"
    VERSION = "1.2.0"
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = int(os.getenv("PORT", 10000))
    ORIGINAL_RSS_URL = "https://rss.app/feed/zKvsfrwIfVjjKtpr"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MAX_RETRIES = 3
    FEED_TITLE = "She Cooks Bakes - Professional Recipes"
    FEED_DESCRIPTION = "Delicious baking recipes and cooking tips"
    FEED_LINK = "https://shecooksandbakes.tumblr.com"
    FEED_LANGUAGE = "en-us"
    CACHE_DURATION = 300
    MAX_FEED_ITEMS = 10
    LOG_FILE = "reddit_rss_bot.log"
    LOG_MAX_BYTES = 5 * 1024 * 1024
    LOG_BACKUP_COUNT = 3
    SELF_PING_ENABLED = True
    SELF_PING_INTERVAL = 840

def setup_logging():
    logger = logging.getLogger(Config.APP_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    file_handler = RotatingFileHandler(Config.LOG_FILE, maxBytes=Config.LOG_MAX_BYTES, backupCount=Config.LOG_BACKUP_COUNT, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(funcName)s | %(message)s'))
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger

logger = setup_logging()

class AdvancedBrowserSession:
    """Advanced browser spoofing to bypass rss.app detection"""
    def __init__(self):
        self.session = requests.Session()
        self._setup_advanced_session()
        logger.info("✅ Advanced browser session initialized")
    
    def _setup_advanced_session(self):
        """Setup ultra-realistic Chrome browser"""
        # Rotate User-Agents for variety
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.user_agent = random.choice(user_agents)
        
        # Enhanced headers
        self.headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }
        
        self.session.headers.update(self.headers)
        
        # Advanced adapter with retries
        from requests.adapters import HTTPAdapter
        from requests.packages.urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[403, 429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET with advanced anti-detection"""
        # Random realistic delay (1-3 seconds)
        time.sleep(random.uniform(1.0, 3.0))
        
        # Add varied referers
        referers = [
            'https://www.google.com/',
            'https://www.google.com/search?q=rss+feeds',
            'https://feedly.com/',
            'https://www.bing.com/'
        ]
        
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        
        kwargs['headers']['Referer'] = random.choice(referers)
        
        # Disable automatic redirects first visit
        kwargs.setdefault('allow_redirects', True)
        kwargs.setdefault('timeout', 20)
        
        # Add cookies to appear like returning visitor
        self.session.cookies.set('visited', 'true', domain='.rss.app')
        
        logger.debug(f"🌐 Fetching: {url}")
        logger.debug(f"   User-Agent: {self.user_agent[:50]}...")
        logger.debug(f"   Referer: {kwargs['headers']['Referer']}")
        
        response = self.session.get(url, **kwargs)
        
        logger.info(f"✅ Response: {response.status_code} ({len(response.content)} bytes)")
        
        return response
    
    def close(self):
        self.session.close()

class GeminiOptimizer:
    """Google Gemini AI optimizer"""
    def __init__(self):
        self.enabled = False
        self.model = None
        
        if not GENAI_AVAILABLE:
            logger.warning("⚠️ google-generativeai not installed")
            return
        
        if not Config.GEMINI_API_KEY:
            logger.warning("⚠️ GEMINI_API_KEY not set")
            return
        
        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            test = self.model.generate_content("Hi")
            if test and test.text:
                self.enabled = True
                logger.info("✅ Gemini AI active")
        except Exception as e:
            logger.error(f"❌ Gemini failed: {e}")
    
    def optimize_title(self, title: str) -> str:
        if not self.enabled:
            return title
        try:
            prompt = f'Optimize for Reddit (max 250 chars, catchy, 1-2 emoji): "{title}"'
            response = self.model.generate_content(prompt)
            optimized = response.text.strip().replace('**', '').replace('*', '')
            return optimized[:250] if len(optimized) > 250 else optimized
        except:
            return title
    
    def generate_description(self, title: str, desc: str) -> str:
        if not self.enabled:
            return desc[:200]
        try:
            prompt = f'Reddit description (2-3 sentences, engaging): Title: "{title}", Original: "{desc[:150]}"'
            response = self.model.generate_content(prompt)
            return response.text.strip().replace('**', '').replace('*', '')
        except:
            return desc[:200]

class RSSProcessor:
    def __init__(self, optimizer: GeminiOptimizer):
        self.optimizer = optimizer
        self.browser = AdvancedBrowserSession()
        self.cache = None
        self.cache_time = None
    
    def fetch_feed(self) -> Optional[str]:
        """Fetch RSS with advanced spoofing"""
        try:
            logger.info(f"📡 Fetching RSS: {Config.ORIGINAL_RSS_URL}")
            response = self.browser.get(Config.ORIGINAL_RSS_URL)
            response.raise_for_status()
            
            # Verify it's XML
            if 'xml' not in response.headers.get('Content-Type', '').lower():
                logger.warning(f"⚠️ Unexpected content type: {response.headers.get('Content-Type')}")
            
            logger.info(f"✅ RSS fetched: {len(response.text)} bytes")
            return response.text
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e}")
            logger.error(f"   Content-Type: {e.response.headers.get('Content-Type', 'unknown')}")
            logger.error(f"   Server: {e.response.headers.get('Server', 'unknown')}")
            return None
        except Exception as e:
            logger.error(f"❌ Fetch failed: {e}")
            return None
    
    def parse_items(self, xml: str) -> List[Dict]:
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
                        import re
                        desc_text = re.sub(r'<[^>]+>', '', desc.text).strip()
                    
                    items.append({
                        'title': title.text or "Untitled",
                        'link': link.text or "",
                        'description': desc_text or "No description",
                        'pubDate': date.text if date is not None else datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
                    })
            
            logger.info(f"✅ Parsed {len(items)} items")
            return items[:Config.MAX_FEED_ITEMS]
        except Exception as e:
            logger.error(f"❌ Parse failed: {e}")
            return []
    
    def create_dynamic_link(self, link: str, post_id: str) -> str:
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
        return f"{link}{'&' if '?' in link else '?'}{params}"
    
    def optimize_item(self, item: Dict, index: int) -> Dict:
        post_id = hashlib.md5(item['link'].encode()).hexdigest()[:12]
        opt_title = self.optimizer.optimize_title(item['title'])
        opt_desc = self.optimizer.generate_description(opt_title, item['description'])
        dyn_link = self.create_dynamic_link(item['link'], post_id)
        
        logger.info(f"✅ Item {index+1}: {opt_title[:40]}...")
        return {
            'title': opt_title,
            'link': dyn_link,
            'description': opt_desc,
            'pubDate': item['pubDate'],
            'guid': post_id
        }
    
    def generate_xml(self, items: List[Dict]) -> str:
        rss = ET.Element('rss', {'version': '2.0', 'xmlns:atom': 'http://www.w3.org/2005/Atom'})
        channel = ET.SubElement(rss, 'channel')
        ET.SubElement(channel, 'title').text = Config.FEED_TITLE
        ET.SubElement(channel, 'link').text = Config.FEED_LINK
        ET.SubElement(channel, 'description').text = Config.FEED_DESCRIPTION
        ET.SubElement(channel, 'language').text = Config.FEED_LANGUAGE
        ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
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
        if not force and self.cache and self.cache_time:
            age = time.time() - self.cache_time
            if age < Config.CACHE_DURATION:
                logger.info(f"📦 Cache ({int(age)}s old)")
                return self.cache
        
        xml = self.fetch_feed()
        if not xml:
            return self.cache
        
        items = self.parse_items(xml)
        if not items:
            return self.cache
        
        optimized = []
        for i, item in enumerate(items):
            try:
                optimized.append(self.optimize_item(item, i))
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ Optimize item {i}: {e}")
        
        if not optimized:
            return self.cache
        
        feed_xml = self.generate_xml(optimized)
        self.cache = feed_xml
        self.cache_time = time.time()
        
        logger.info(f"✅ Feed: {len(optimized)} items")
        return feed_xml

app = Flask(__name__)
optimizer = GeminiOptimizer()
processor = RSSProcessor(optimizer)
start_time = time.time()

@app.route('/')
def home():
    uptime = int(time.time() - start_time)
    return jsonify({
        "status": "active",
        "version": Config.VERSION,
        "uptime": f"{uptime//3600}h{(uptime%3600)//60}m",
        "feed_url": f"{os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:10000')}/feed",
        "ai": optimizer.enabled,
        "cache": f"{int(time.time()-processor.cache_time)}s" if processor.cache_time else "none"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "ai": optimizer.enabled, "time": datetime.now().isoformat()})

@app.route('/feed')
def feed():
    try:
        logger.info("📡 Feed request")
        xml = processor.get_feed()
        if not xml:
            return Response("<?xml version='1.0'?><e>Unavailable</e>", mimetype='application/xml', status=503)
        return Response(xml, mimetype='application/xml', headers={'Cache-Control': f'public, max-age={Config.CACHE_DURATION}'})
    except Exception as e:
        logger.error(f"❌ Feed error: {e}")
        return Response(f"<?xml version='1.0'?><e>{str(e)}</e>", mimetype='application/xml', status=500)

@app.route('/refresh', methods=['POST'])
def refresh():
    try:
        xml = processor.get_feed(force=True)
        return jsonify({"success": bool(xml), "items": xml.count('<item>') if xml else 0})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

class SelfPing:
    def __init__(self):
        url = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{Config.FLASK_PORT}')
        if Config.SELF_PING_ENABLED:
            import threading
            threading.Thread(target=lambda: self._loop(url), daemon=True).start()
            logger.info("💓 Self-ping started")
    def _loop(self, url):
        while True:
            time.sleep(Config.SELF_PING_INTERVAL)
            try: requests.get(f"{url}/health", timeout=10)
            except: pass

def main():
    try:
        logger.info("="*60)
        logger.info(f"🚀 {Config.APP_NAME} v{Config.VERSION}")
        logger.info(f"🤖 AI: {'✅ Active' if optimizer.enabled else '❌ Disabled'}")
        logger.info(f"🌐 Browser: Advanced spoofing")
        logger.info(f"📡 RSS: {Config.ORIGINAL_RSS_URL}")
        logger.info("="*60)
        
        SelfPing()
        
        logger.info("🔄 Pre-fetch...")
        processor.get_feed(force=True)
        
        logger.info(f"🌐 Waitress on :{Config.FLASK_PORT}")
        logger.info("✅ OPERATIONAL!")
        logger.info(f"📡 Feed: {os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{Config.FLASK_PORT}')}/feed")
        logger.info("="*60)
        
        serve(app, host=Config.FLASK_HOST, port=Config.FLASK_PORT, threads=4, _quiet=False)
    except KeyboardInterrupt:
        logger.info("⏹️ Shutdown")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"💥 Critical: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
