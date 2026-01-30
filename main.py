#!/usr/bin/env python3
"""
Reddit RSS Bot v1.1.2
✅ Auto-posts to Reddit via RSS + IFTTT
✅ Google Gemini AI for title/description optimization (FIXED)
✅ Dynamic links to avoid spam detection
✅ Professional RSS feed generation
✅ Browser spoofing to bypass rss.app detection
✅ FIXED: Gemini AI now works with google-generativeai package
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

# Import Gemini AI (correct way)
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

class Config:
    APP_NAME = "Reddit RSS Bot"
    VERSION = "1.1.2"
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = int(os.getenv("PORT", 10000))
    
    # RSS Source
    ORIGINAL_RSS_URL = "https://rss.app/feed/zKvsfrwIfVjjKtpr"
    
    # Gemini AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MAX_RETRIES = 3
    GEMINI_RETRY_DELAY = 5
    
    # RSS Feed Settings
    FEED_TITLE = "She Cooks Bakes - Professional Recipes"
    FEED_DESCRIPTION = "Delicious baking recipes and cooking tips"
    FEED_LINK = "https://shecooksandbakes.tumblr.com"
    FEED_LANGUAGE = "en-us"
    
    # Cache Settings
    CACHE_DURATION = 300  # 5 minutes
    MAX_FEED_ITEMS = 10
    
    # Logging
    LOG_FILE = "reddit_rss_bot.log"
    LOG_MAX_BYTES = 5 * 1024 * 1024
    LOG_BACKUP_COUNT = 3
    
    # Self-ping
    SELF_PING_ENABLED = True
    SELF_PING_INTERVAL = 840  # 14 minutes
    
    # Browser Spoofing - Realistic Chrome headers
    BROWSER_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

def setup_logging():
    logger = logging.getLogger(Config.APP_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)s | %(message)s'
    ))
    
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger

logger = setup_logging()

class BrowserSession:
    """Manages realistic browser session with spoofing"""
    
    def __init__(self):
        self.session = requests.Session()
        self._setup_session()
        logger.info("✅ Browser session initialized (Chrome spoofing)")
    
    def _setup_session(self):
        """Setup session to mimic real Chrome browser"""
        # Set default headers
        self.session.headers.update(Config.BROWSER_HEADERS)
        
        # Configure connection pooling for realistic behavior
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET request with browser spoofing"""
        # Add referer for realistic browsing pattern
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        
        # Simulate coming from Google search
        kwargs['headers']['Referer'] = 'https://www.google.com/'
        
        # Random delay to mimic human behavior (0.5-2 seconds)
        time.sleep(random.uniform(0.5, 2.0))
        
        # Make request
        response = self.session.get(url, **kwargs)
        
        logger.debug(f"🌐 Browser request: {url} → {response.status_code}")
        return response
    
    def close(self):
        """Close session"""
        self.session.close()

class GeminiOptimizer:
    """Google Gemini AI for content optimization - FIXED VERSION"""
    
    def __init__(self):
        self.enabled = False
        self.model = None
        
        # Check if package is available
        if not GENAI_AVAILABLE:
            logger.warning("⚠️ google-generativeai package not installed")
            logger.warning("⚠️ Run: pip install google-generativeai")
            return
        
        # Check if API key is set
        if not Config.GEMINI_API_KEY:
            logger.warning("⚠️ GEMINI_API_KEY not set - using fallback mode")
            logger.warning("⚠️ Set GEMINI_API_KEY environment variable to enable AI")
            return
        
        # Initialize Gemini
        try:
            # Configure API key
            genai.configure(api_key=Config.GEMINI_API_KEY)
            
            # Create model instance
            self.model = genai.GenerativeModel('gemini-pro')
            
            # Test the model with a simple prompt
            logger.info("🧪 Testing Gemini AI connection...")
            test_response = self.model.generate_content("Hello")
            
            if test_response and test_response.text:
                self.enabled = True
                logger.info("✅ Gemini AI initialized and working!")
                logger.info(f"   Test response: {test_response.text[:50]}...")
            else:
                logger.error("❌ Gemini AI test failed - no response")
                
        except Exception as e:
            logger.error(f"❌ Gemini initialization failed: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Make sure GEMINI_API_KEY is valid")
            self.enabled = False
    
    def optimize_title(self, original_title: str) -> str:
        """Optimize title for Reddit engagement"""
        if not self.enabled or not self.model:
            logger.debug(f"⚠️ AI disabled, using original title: {original_title}")
            return original_title
        
        try:
            prompt = f'''Optimize this recipe/cooking title for Reddit to maximize engagement.

Original title: "{original_title}"

Requirements:
1. Keep it under 250 characters (Reddit limit)
2. Make it catchy and clickable
3. Use power words (Amazing, Perfect, Easy, Pro, Secret, etc.)
4. Add emoji if appropriate (max 2)
5. Keep the core topic clear

Return ONLY the optimized title, nothing else.'''

            logger.debug(f"🤖 Sending title to Gemini: {original_title[:30]}...")
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                logger.warning("⚠️ Gemini returned empty response for title")
                return original_title
            
            optimized = response.text.strip()
            
            # Remove markdown formatting if present
            optimized = optimized.replace('**', '').replace('*', '')
            
            # Validate length
            if len(optimized) > 250:
                optimized = optimized[:247] + "..."
            
            logger.info(f"✅ Title optimized by AI")
            logger.debug(f"   Original: {original_title[:40]}...")
            logger.debug(f"   Optimized: {optimized[:40]}...")
            
            return optimized
            
        except Exception as e:
            logger.error(f"❌ Gemini title optimization failed: {e}")
            logger.debug(f"   Falling back to original title")
            return original_title
    
    def generate_description(self, title: str, original_desc: str) -> str:
        """Generate engaging Reddit-friendly description"""
        if not self.enabled or not self.model:
            logger.debug(f"⚠️ AI disabled, using fallback description")
            return self._fallback_description(original_desc)
        
        try:
            prompt = f'''Create a SHORT, engaging Reddit post description for this recipe.

Title: "{title}"
Original: "{original_desc[:200]}"

Requirements:
1. 2-3 sentences maximum
2. Make it conversational and friendly
3. Highlight what makes this recipe special
4. End with a call-to-action
5. NO emojis in description (title only)

Return ONLY the description, nothing else.'''

            logger.debug(f"🤖 Generating description with Gemini...")
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                logger.warning("⚠️ Gemini returned empty response for description")
                return self._fallback_description(original_desc)
            
            description = response.text.strip()
            
            # Remove markdown formatting if present
            description = description.replace('**', '').replace('*', '')
            
            logger.info(f"✅ Description generated by AI: {len(description)} chars")
            
            return description
            
        except Exception as e:
            logger.error(f"❌ Gemini description failed: {e}")
            logger.debug(f"   Falling back to original description")
            return self._fallback_description(original_desc)
    
    def _fallback_description(self, original: str) -> str:
        """Fallback description when AI is unavailable"""
        if len(original) > 200:
            return original[:197] + "..."
        return original

class RSSFeedProcessor:
    """Process and transform RSS feeds"""
    
    def __init__(self, gemini_optimizer: GeminiOptimizer):
        self.optimizer = gemini_optimizer
        self.browser = BrowserSession()
        self.cache = None
        self.cache_time = None
    
    def fetch_original_feed(self) -> Optional[str]:
        """Fetch original RSS feed with browser spoofing"""
        try:
            logger.info(f"📡 Fetching RSS (as Chrome browser): {Config.ORIGINAL_RSS_URL}")
            
            # Use browser session with spoofing
            response = self.browser.get(
                Config.ORIGINAL_RSS_URL,
                timeout=15,
                allow_redirects=True
            )
            
            response.raise_for_status()
            
            logger.info(f"✅ RSS fetched successfully: {len(response.text)} bytes")
            logger.debug(f"   Response headers: {dict(response.headers)}")
            
            return response.text
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP Error {e.response.status_code}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"   Response: {e.response.text[:200]}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout fetching RSS (exceeded 15s)")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Connection error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ RSS fetch failed: {e}")
            return None
    
    def parse_feed_items(self, rss_content: str) -> List[Dict]:
        """Parse RSS XML and extract items"""
        try:
            root = ET.fromstring(rss_content)
            items = []
            
            # Find all item elements (works for both RSS 2.0 and Atom)
            for item in root.findall('.//item'):
                try:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    desc_elem = item.find('description')
                    pubdate_elem = item.find('pubDate')
                    
                    if title_elem is not None and link_elem is not None:
                        # Extract image from description if present
                        image_url = None
                        description_text = ""
                        
                        if desc_elem is not None and desc_elem.text:
                            description_text = desc_elem.text
                            # Try to extract image URL from HTML
                            if '<img' in description_text:
                                try:
                                    import re
                                    img_match = re.search(r'<img[^>]+src="([^"]+)"', description_text)
                                    if img_match:
                                        image_url = img_match.group(1)
                                    # Remove HTML tags from description
                                    description_text = re.sub(r'<[^>]+>', '', description_text)
                                    description_text = description_text.strip()
                                except:
                                    pass
                        
                        item_data = {
                            'title': title_elem.text or "Untitled",
                            'link': link_elem.text or "",
                            'description': description_text or "No description",
                            'image': image_url,
                            'pubDate': pubdate_elem.text if pubdate_elem is not None else datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
                        }
                        
                        items.append(item_data)
                        
                except Exception as e:
                    logger.warning(f"⚠️ Failed to parse item: {e}")
                    continue
            
            logger.info(f"✅ Parsed {len(items)} items from RSS")
            return items[:Config.MAX_FEED_ITEMS]
            
        except Exception as e:
            logger.error(f"❌ RSS parsing failed: {e}")
            return []
    
    def create_dynamic_link(self, original_link: str, post_id: str) -> str:
        """Create dynamic link to avoid spam detection"""
        # Generate unique parameters
        timestamp = int(time.time())
        random_token = hashlib.md5(f"{post_id}{timestamp}".encode()).hexdigest()[:8]
        
        params = {
            'source': 'reddit',
            'utm_campaign': 'rss_auto',
            'utm_medium': 'social',
            'post_id': post_id,
            'ref': random_token,
            't': timestamp
        }
        
        separator = '&' if '?' in original_link else '?'
        dynamic_link = f"{original_link}{separator}{urlencode(params)}"
        
        return dynamic_link
    
    def optimize_feed_item(self, item: Dict, index: int) -> Dict:
        """Optimize a single feed item with Gemini AI"""
        post_id = hashlib.md5(item['link'].encode()).hexdigest()[:12]
        
        # Optimize title
        optimized_title = self.optimizer.optimize_title(item['title'])
        
        # Generate description
        optimized_desc = self.optimizer.generate_description(
            optimized_title,
            item['description']
        )
        
        # Create dynamic link
        dynamic_link = self.create_dynamic_link(item['link'], post_id)
        
        # Build full description with image if available
        full_description = optimized_desc
        if item.get('image'):
            full_description = f"{optimized_desc}\n\n[Image: {item['image']}]"
        
        optimized_item = {
            'title': optimized_title,
            'link': dynamic_link,
            'description': full_description,
            'pubDate': item['pubDate'],
            'guid': post_id,
            'original_link': item['link']
        }
        
        logger.info(f"✅ Optimized item {index + 1}: {optimized_title[:50]}...")
        return optimized_item
    
    def generate_rss_xml(self, items: List[Dict]) -> str:
        """Generate optimized RSS 2.0 XML feed"""
        # Create RSS root
        rss = ET.Element('rss', {
            'version': '2.0',
            'xmlns:atom': 'http://www.w3.org/2005/Atom'
        })
        
        channel = ET.SubElement(rss, 'channel')
        
        # Channel metadata
        ET.SubElement(channel, 'title').text = Config.FEED_TITLE
        ET.SubElement(channel, 'link').text = Config.FEED_LINK
        ET.SubElement(channel, 'description').text = Config.FEED_DESCRIPTION
        ET.SubElement(channel, 'language').text = Config.FEED_LANGUAGE
        ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        ET.SubElement(channel, 'generator').text = f"{Config.APP_NAME} v{Config.VERSION}"
        
        # Self link
        atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link', {
            'href': f"{os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:10000')}/feed",
            'rel': 'self',
            'type': 'application/rss+xml'
        })
        
        # Add optimized items
        for item_data in items:
            item = ET.SubElement(channel, 'item')
            ET.SubElement(item, 'title').text = item_data['title']
            ET.SubElement(item, 'link').text = item_data['link']
            ET.SubElement(item, 'description').text = item_data['description']
            ET.SubElement(item, 'pubDate').text = item_data['pubDate']
            ET.SubElement(item, 'guid', {'isPermaLink': 'false'}).text = item_data['guid']
        
        # Convert to string
        xml_string = ET.tostring(rss, encoding='unicode', method='xml')
        
        # Add XML declaration
        final_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}'
        
        logger.info(f"✅ Generated RSS XML: {len(final_xml)} bytes")
        return final_xml
    
    def get_optimized_feed(self, force_refresh: bool = False) -> Optional[str]:
        """Get optimized RSS feed (with caching)"""
        # Check cache
        if not force_refresh and self.cache and self.cache_time:
            age = time.time() - self.cache_time
            if age < Config.CACHE_DURATION:
                logger.info(f"📦 Using cached feed ({int(age)}s old)")
                return self.cache
        
        # Fetch original feed (with browser spoofing)
        original_rss = self.fetch_original_feed()
        if not original_rss:
            logger.error("❌ Cannot generate feed: fetch failed")
            return self.cache  # Return cached version if available
        
        # Parse items
        items = self.parse_feed_items(original_rss)
        if not items:
            logger.error("❌ Cannot generate feed: no items parsed")
            return self.cache
        
        # Optimize items
        optimized_items = []
        for index, item in enumerate(items):
            try:
                optimized = self.optimize_feed_item(item, index)
                optimized_items.append(optimized)
                time.sleep(1)  # Rate limiting for Gemini API
            except Exception as e:
                logger.error(f"❌ Failed to optimize item {index}: {e}")
                continue
        
        if not optimized_items:
            logger.error("❌ No items were successfully optimized")
            return self.cache
        
        # Generate XML
        rss_xml = self.generate_rss_xml(optimized_items)
        
        # Update cache
        self.cache = rss_xml
        self.cache_time = time.time()
        
        logger.info(f"✅ Feed generated: {len(optimized_items)} items")
        return rss_xml
    
    def __del__(self):
        """Cleanup browser session"""
        if hasattr(self, 'browser'):
            self.browser.close()

# Initialize Flask app
app = Flask(__name__)
gemini_optimizer = GeminiOptimizer()
rss_processor = RSSFeedProcessor(gemini_optimizer)
start_time = time.time()

@app.route('/')
def home():
    """Service status page"""
    uptime = int(time.time() - start_time)
    return jsonify({
        "status": "active",
        "service": Config.APP_NAME,
        "version": Config.VERSION,
        "uptime": f"{uptime // 3600}h {(uptime % 3600) // 60}m",
        "feed_url": f"{os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:10000')}/feed",
        "ai_enabled": gemini_optimizer.enabled,
        "ai_model": "gemini-pro" if gemini_optimizer.enabled else "disabled",
        "browser_spoofing": "Chrome 120.0 (Windows 10)",
        "cache_age": f"{int(time.time() - rss_processor.cache_time)}s" if rss_processor.cache_time else "none",
        "original_rss": Config.ORIGINAL_RSS_URL
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ai": "enabled" if gemini_optimizer.enabled else "disabled",
        "browser": "Chrome/120.0"
    })

@app.route('/feed')
def feed():
    """Optimized RSS feed endpoint (for IFTTT)"""
    try:
        logger.info("📡 Feed requested")
        
        # Get optimized feed
        rss_xml = rss_processor.get_optimized_feed()
        
        if not rss_xml:
            logger.error("❌ Feed generation failed")
            return Response(
                "<?xml version='1.0'?><e>Feed temporarily unavailable</e>",
                mimetype='application/xml',
                status=503
            )
        
        logger.info("✅ Feed delivered successfully")
        return Response(
            rss_xml,
            mimetype='application/xml',
            headers={
                'Cache-Control': f'public, max-age={Config.CACHE_DURATION}',
                'X-Generated-By': f'{Config.APP_NAME} v{Config.VERSION}'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Feed endpoint error: {e}")
        return Response(
            f"<?xml version='1.0'?><e>{str(e)}</e>",
            mimetype='application/xml',
            status=500
        )

@app.route('/refresh', methods=['POST'])
def refresh():
    """Force refresh feed cache"""
    try:
        logger.info("🔄 Manual refresh requested")
        rss_xml = rss_processor.get_optimized_feed(force_refresh=True)
        
        if rss_xml:
            return jsonify({
                "success": True,
                "message": "Feed refreshed successfully",
                "items": rss_xml.count('<item>'),
                "ai_enabled": gemini_optimizer.enabled
            })
        else:
            return jsonify({
                "success": False,
                "message": "Feed refresh failed"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Refresh error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

class SelfPingService:
    """Keep service alive on Render"""
    
    def __init__(self):
        self.url = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{Config.FLASK_PORT}')
        if Config.SELF_PING_ENABLED:
            import threading
            threading.Thread(target=self._ping_loop, daemon=True).start()
            logger.info("💓 Self-ping service started")
    
    def _ping_loop(self):
        while True:
            time.sleep(Config.SELF_PING_INTERVAL)
            try:
                requests.get(f"{self.url}/health", timeout=10)
                logger.debug("💓 Self-ping successful")
            except:
                pass

def main():
    try:
        logger.info("=" * 60)
        logger.info(f"🚀 {Config.APP_NAME} v{Config.VERSION}")
        logger.info(f"🤖 AI Engine: Google Gemini Pro")
        logger.info(f"   Status: {'✅ ACTIVE' if gemini_optimizer.enabled else '❌ DISABLED'}")
        if not gemini_optimizer.enabled:
            if not GENAI_AVAILABLE:
                logger.warning("   Reason: google-generativeai package not installed")
                logger.warning("   Fix: pip install google-generativeai")
            elif not Config.GEMINI_API_KEY:
                logger.warning("   Reason: GEMINI_API_KEY not set")
                logger.warning("   Fix: Set GEMINI_API_KEY environment variable")
        logger.info(f"🌐 Browser: Chrome 120.0 (Windows 10) - Spoofing Active")
        logger.info(f"📡 Source RSS: {Config.ORIGINAL_RSS_URL}")
        logger.info(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # Start self-ping service
        SelfPingService()
        
        # Pre-generate first feed
        logger.info("🔄 Pre-generating initial feed...")
        rss_processor.get_optimized_feed(force_refresh=True)
        
        logger.info(f"🌐 Starting Waitress server on port {Config.FLASK_PORT}...")
        logger.info("=" * 60)
        logger.info("✅ SYSTEM OPERATIONAL!")
        logger.info("=" * 60)
        logger.info(f"📡 Feed URL: {os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{Config.FLASK_PORT}')}/feed")
        logger.info("📝 Use this URL in IFTTT RSS trigger")
        logger.info("=" * 60)
        
        serve(
            app,
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            threads=4,
            channel_timeout=60,
            cleanup_interval=30,
            _quiet=False
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"💥 Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
