import logging
import os
import sys
import random
import re
import html
import textwrap
from io import BytesIO
from datetime import datetime
import xml.etree.ElementTree as ET

# --- ספריות חיצוניות ---
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects 
from PIL import Image
from dotenv import load_dotenv

# --- ייבוא מודולים חדשים ---
from bs4 import BeautifulSoup
from google import genai
from google.genai import types 

# ---
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    print("[X] Missing libraries. Run: pip install python-bidi arabic-reshaper")
    sys.exit()

try:
    from instagrapi import Client
    from moviepy.editor import ImageClip, AudioFileClip
except ImportError as e:
    print(f"[X] Missing library: {e}")
    sys.exit()

# ==========================================
#      תיקון קריטי לטרמינל & נתיבים
# ==========================================
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "Rubik-Bold.ttf")

# ==========================================
# 🚨 הגדרה ידנית של המפתחות (עוקף את .env) 🚨
# ==========================================

# 👇👇👇 תדביק את המפתח הארוך שלך כאן בין הגרשיים 👇👇👇
MY_GEMINI_KEY = "AIzaSyDjy7ijfAyuhYQBNKNPwTi9TwuKfGUB5s0" 

# 👇👇👇 פרטי אינסטגרם 👇👇👇
MY_INSTA_USER = "Israel.Finance.Daily"
MY_INSTA_PASS = "kvetchooch123"

print(f"DEBUG: Manually loaded key: {MY_GEMINI_KEY[:5]}...")

# ==========================================
#          הגדרת קליינט Gemini
# ==========================================
try:
    # אנחנו מכניסים את המשתנה הידני ישירות לקליינט
    GENAI_CLIENT = genai.Client(api_key=MY_GEMINI_KEY)
    
    # בדיקה פשוטה שהמפתח קיים
    if not MY_GEMINI_KEY or "xxxx" in MY_GEMINI_KEY:
         print("[!] WARNING: נראה שלא הדבקת את המפתח האמיתי בקוד!")
    else:
        print("[V] Gemini Client Initialized.")
        
except Exception as e:
    print(f"[X] GEMINI SETUP ERROR: {e}")
    GENAI_CLIENT = None

# ==========================================
#          הגדרות עיצוב ותצורה
# ==========================================
CONFIG = {
    "INSTA_USERNAME": MY_INSTA_USER, # לוקח מהמשתנה הידני למעלה
    "INSTA_PASSWORD": MY_INSTA_PASS, # לוקח מהמשתנה הידני למעלה
    "UPLOAD_TO_INSTAGRAM": False,
    "HISTORY_FILE": "news_history.txt",
    "SESSION_FILE": "insta_session.json",
    "THEME_COLOR": "#a80000",
    "BG_OVERLAY": 0.5,        
    "FONT_PATH": FONT_PATH
}

logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)


# ==========================================
#          פונקציות עזר - עיבוד תמונה וטקסט
# ==========================================

def smart_crop_image(img, target_width=1080, target_height=1920):
    """
    מבצע חיתוך חכם (Center Crop) כדי שהתמונה תמלא את המסך בלי להימרח.
    """
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height

    if img_ratio > target_ratio:
        # התמונה רחבה מדי: משנים גובה וחותכים בצדדים
        new_height = target_height
        new_width = int(new_height * img_ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        left = (new_width - target_width) / 2
        img = img.crop((left, 0, left + target_width, target_height))
    else:
        # התמונה גבוהה מדי: משנים רוחב וחותכים למעלה/למטה
        new_width = target_width
        new_height = int(new_width / img_ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        top = (new_height - target_height) / 4 
        img = img.crop((0, top, target_width, top + target_height))
        
    return img
# יש להוסיף את זה למעלה באימפורטים:
from google.genai import types 

def generate_reel_description(title, description):
    """הגרסה החכמה: קודם בודקת איזה מודל קיים בחשבון, ואז משתמשת בו."""
    
    # ==========================================
    # 👇👇👇 המפתח שלך 👇👇👇
    # ==========================================
    raw_key = "AIzaSyDjy7ijfAyuhYQBNKNPwTi9TwuKfGUB5s0" 
    # ==========================================

    clean_key = re.sub(r'[^a-zA-Z0-9_\-]', '', raw_key)
    
    # שלב 1: מציאת מודל זמין (כמו שעשית בדפדפן)
    print("   [Gemini] Auto-detecting available models...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
    
    chosen_model = "models/gemini-1.5-flash" # ברירת מחדל
    
    try:
        list_resp = requests.get(list_url, timeout=10)
        if list_resp.status_code == 200:
            data = list_resp.json()
            # מחפש את המודל הראשון שיודע לייצר תוכן
            for m in data.get('models', []):
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    chosen_model = m['name'] # לוקח את השם המדויק מהרשימה
                    print(f"   [V] Found valid model: {chosen_model}")
                    break
        else:
            print(f"   [!] Could not list models (Error {list_resp.status_code}). Trying default.")
            
    except Exception as e:
        print(f"   [!] List models failed: {e}")

    # שלב 2: שימוש במודל שנמצא
    generate_url = f"https://generativelanguage.googleapis.com/v1beta/{chosen_model}:generateContent?key={clean_key}"
    
    prompt_text = f"""
    כתוב תיאור (Caption) קצר וקליט לסרטון רילס באינסטגרם.
    נושא: חדשות טק ופיננסים. כותרת: "{title}".
    כתוב בעברית, עד 3 משפטים, בלי מרכאות, עם האשטאגים.
    """
    
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    try:
        print(f"   [Gemini] Sending request to: {chosen_model}...")
        response = requests.post(generate_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result:
                text = result['candidates'][0]['content']['parts'][0]['text']
                print("   [V] GEMINI SUCCESS! Description generated.")
                return text
            else:
                print(f"   [X] Empty response: {result}")
        else:
            print(f"   [X] Google Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"   [X] Connection failed: {e}")

    return f"חדשות: {title}\n\n{description[:500]}..."
def get_custom_font(size):
    if os.path.exists(CONFIG["FONT_PATH"]):
        return fm.FontProperties(fname=CONFIG["FONT_PATH"], size=size)
    else:
        return fm.FontProperties(family="Arial", weight="bold", size=size)

def expand_abbreviations(text):
    if not text: return ""
    text = text.replace(" ד'", " דולר")
    text = text.replace(" מיל'", " מיליון")
    text = text.replace(" א'", " אלף")
    text = text.replace('"', '') 
    text = text.replace("$", " דולר")
    return text

def apply_bidi(text):
    if not text: return ""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except Exception:
        return text

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return html.unescape(re.sub(cleanr, '', raw_html))

# ==========================================
#          ניהול היסטוריה וחיפוש
# ==========================================
def get_used_titles():
    if not os.path.exists(CONFIG["HISTORY_FILE"]): return []
    try:
        with open(CONFIG["HISTORY_FILE"], "r", encoding="utf-8") as f:
            return f.read().splitlines()
    except: return []

def save_title_to_history(title):
    try:
        with open(CONFIG["HISTORY_FILE"], "a", encoding="utf-8") as f:
            f.write(title + "\n")
    except: pass

def get_tycoons_list():
    return [
        {
            "name": "Bitcoin", 
            "search_query": "ביטקוין", 
            "hashtags": "#ביטקוין #קריפטו #בלוקציין #השקעות", 
            "top_title": "עולם הקריפטו:", 
            "bottom_title": "עדכוני השוק", 
            "images": [
                "https://cdn.pixabay.com/photo/2018/01/18/07/31/bitcoin-3089728_1280.jpg",
                "https://images.pexels.com/photos/844124/pexels-photo-844124.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1"
            ]
        },
        {
            "name": "Elon Musk", 
            "search_query": "אילון מאסק",
            "hashtags": "#אילוןמאסק #טסלה #SpaceX #חדשנות", 
            "top_title": "אילון מאסק:", 
            "bottom_title": "טק & חדשנות", 
            "images": [
                "https://cdn.britannica.com/45/223045-050-A6453D5D/Telsa-CEO-Elon-Musk-2014.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Elon_Musk_Royal_Society_%28crop2%29.jpg/800px-Elon_Musk_Royal_Society_%28crop2%29.jpg"
            ]
        },
        {
            "name": "Nvidia", 
            "search_query": "אנבידיה", 
            "hashtags": "#אנבידיה #AI #שבבים #טכנולוגיה", 
            "top_title": "הענקית הירוקה:", 
            "bottom_title": "חדשות השבבים", 
            "images": [
                "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/NVIDIA_logo.svg/1024px-NVIDIA_logo.svg.png",
                "https://cdn.pixabay.com/photo/2023/11/04/12/37/gpu-8364736_1280.jpg"
            ]
        },
    ]

def get_full_article_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        article_body = soup.find('article')
        if article_body:
            text = article_body.get_text(" ", strip=True)
        else:
            paragraphs = soup.find_all('p')
            text = " ".join([p.get_text(" ", strip=True) for p in paragraphs])
            
        return text if len(text) > 100 else None
    except Exception as e:
        print(f"   [!] Error scraping: {e}")
        return None

def get_news_from_google(query):
    print(f">> Searching news for: {query}...")
    trusted_sites = ["globes.co.il", "calcalist.co.il", "themarker.com", "bizportal.co.il", "ynet.co.il", "maariv.co.il", "ice.co.il"]
    sites_query = " OR ".join([f"site:{site}" for site in trusted_sites])
    rss_url = f"https://news.google.com/rss/search?q={query} ({sites_query})&hl=he&gl=IL&ceid=IL:he"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(rss_url, headers=headers, timeout=10)
        root = ET.fromstring(response.content)
    except Exception as e:
        print(f"[!] RSS Error: {e}")
        return None

    items = root.findall('./channel/item')
    if not items:
        print("   [!] No news found.")
        return None

    used_titles = get_used_titles()

    for item in items:
        title = item.find('title').text
        clean_t = title.split(" - ")[0]
        if clean_t in used_titles: continue
        if any(w in title for w in ["דעה", "פודקאסט", "בלוג", "חסות"]): continue
        if len(clean_t) < 15: continue

        link = item.find('link').text
        print(f"   [V] Found candidate: {clean_t}")
        full_text = get_full_article_content(link)
        description = full_text if full_text else clean_html(item.find('description').text or "")
        return {"title": clean_t, "description": description, "link": link}
    return None

# ==========================================
#          יצירת תמונה (העיצוב המתוקן)
# ==========================================
def create_visual_content():
    figures = get_tycoons_list()
    random.shuffle(figures)
    
    data = None
    source_img = None
    
    for fig_item in figures:
        news = get_news_from_google(fig_item['search_query'])
        if news:
            try:
                chosen_image_url = random.choice(fig_item['images'])
                print(f"   [Image] Downloading: {chosen_image_url[:40]}...")
                resp = requests.get(chosen_image_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                
                raw_img = Image.open(BytesIO(resp.content))
                source_img = smart_crop_image(raw_img, 1080, 1920) 
                
                data = fig_item
                data.update(news)
                break
            except Exception as e:
                print(f"   [!] Image download failed: {e}")
                continue
            
    if not data:
        print("[X] Failed to find valid news.")
        return None, None, None

    save_title_to_history(data['title'])
    
    # 1. יצירת קנבס
    fig, ax = plt.subplots(figsize=(9, 16), dpi=120)
    ax.set_facecolor('black')
    
    ax.imshow(source_img, extent=[0, 1080, 1920, 0])
    ax.set_xlim(0, 1080)
    ax.set_ylim(1920, 0)
    ax.axis('off')
    
    # שכבה שחורה חצי שקופה
    ax.add_patch(patches.Rectangle((0, 0), 1080, 1920, color='black', alpha=CONFIG["BG_OVERLAY"]))

    # 2. לוגו
    logo_text = ax.text(540, 160, "israel.finance.daily", color=CONFIG["THEME_COLOR"], ha='center', 
            fontproperties=get_custom_font(40))
    logo_text.set_path_effects([path_effects.withStroke(linewidth=3, foreground='black')])

    # 3. מסגרת לבנה
    rect_width = 980
    rect_height = 800
    rect_x = (1080 - rect_width) / 2
    rect_y = 900
    rect_center_x = rect_x + (rect_width / 2)
    rect_center_y = rect_y + (rect_height / 2)

    ax.text(540, rect_y - 80, apply_bidi(data['top_title']), color='#cccccc', ha='center', fontproperties=get_custom_font(50))

    rect = patches.Rectangle((rect_x, rect_y), rect_width, rect_height, linewidth=5, edgecolor='white', facecolor='none')
    ax.add_patch(rect)
    ax.add_patch(patches.Rectangle((rect_x, rect_y), rect_width, rect_height, color='black', alpha=0.3))

    # 4. כותרת ראשית חכמה
    expanded_title = expand_abbreviations(data['title'])
    title_len = len(expanded_title)
    
    if title_len > 90:
        dynamic_font_size = 36
        dynamic_wrap_width = 26
    elif title_len > 60:
        dynamic_font_size = 42
        dynamic_wrap_width = 22
    else:
        dynamic_font_size = 50
        dynamic_wrap_width = 18
        
    wrapped_title = textwrap.wrap(expanded_title, width=dynamic_wrap_width) 
    formatted_title = "\n".join([apply_bidi(line) for line in wrapped_title])
    
    main_text = ax.text(rect_center_x, rect_center_y - 40, formatted_title, color='white', ha='center', va='center',
            fontproperties=get_custom_font(dynamic_font_size))
    main_text.set_path_effects([path_effects.SimpleLineShadow(offset=(2, -2), alpha=0.5), path_effects.Normal()])

    # 5. באנר תחתון
    banner_height = 120
    banner_y = rect_y + rect_height - banner_height - 30
    ax.add_patch(patches.Rectangle((rect_x + 50, banner_y), rect_width - 100, banner_height, color=CONFIG["THEME_COLOR"]))
    
    ax.text(rect_center_x, banner_y + (banner_height / 2) + 10, apply_bidi(data['bottom_title']), 
            color='white', ha='center', va='center', fontproperties=get_custom_font(40))

    # שמירה
    t_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    img_filename = f"output_{t_str}.jpg"
    vid_filename = f"reel_{t_str}.mp4"
    
    plt.savefig(img_filename, bbox_inches='tight', pad_inches=0)
    plt.close()
    
    return img_filename, vid_filename, data

# ==========================================
#          יצירת וידאו והעלאה
# ==========================================
def create_video(img_path, vid_path):
    print(f">> Creating video from {img_path}...")
    folder = os.path.dirname(os.path.abspath(__file__))
    
    all_files = os.listdir(folder)
    audio_files = [os.path.join(folder, f) for f in all_files if f.lower().endswith(('.mp3', '.wav'))]
    
    if not audio_files:
        print("[!] ERROR: No .mp3 files found in folder!")
        return False

    try:
        audio_path = random.choice(audio_files)
        print(f"   [Music] Selected: {os.path.basename(audio_path)}")
        
        image_clip = ImageClip(img_path)
        audio_clip = AudioFileClip(audio_path)
        
        # אורך הוידאו = אורך השיר המלא
        video_duration = audio_clip.duration
        
        final_clip = image_clip.set_duration(video_duration).set_audio(audio_clip)
        
        final_clip.write_videofile(vid_path, fps=24, codec="libx264", audio_codec="aac", audio_bitrate="192k", logger=None)
        print(f"   [V] Video saved: {vid_path}")
        return True
    except Exception as e:
        print(f"[X] Video Error: {e}")
        return False

def upload_to_instagram(video_path, caption):
    print("\n>> Instagram Login...")
    cl = Client()
    try:
        if os.path.exists(CONFIG["SESSION_FILE"]):
            cl.load_settings(CONFIG["SESSION_FILE"])
            cl.login(CONFIG["INSTA_USERNAME"], CONFIG["INSTA_PASSWORD"])
            print("   [V] Logged in via Session!")
        else:
            cl.login(CONFIG["INSTA_USERNAME"], CONFIG["INSTA_PASSWORD"])
            cl.dump_settings(CONFIG["SESSION_FILE"])
            print("   [V] New login successful & Session saved.")
    except Exception as e:
        print(f"[X] Login Failed: {e}")
        return

    print(f">> Uploading Reel: {video_path}")
    try:
        media = cl.clip_upload(video_path, caption)
        print(f"[V] SUCCESS! Reel uploaded. Code: {media.code}")
    except Exception as e:
        print(f"[X] Upload Failed: {e}")

# ==========================================
#          Main
# ==========================================
if __name__ == "__main__":
    if not CONFIG["INSTA_USERNAME"] or not CONFIG["INSTA_PASSWORD"]:
        print("[!] ERROR: Please set INSTA_USER and INSTA_PASS in .env file")
        sys.exit()

    print("--- Starting Auto-News-Reel (Smart Crop) ---")
    
    img_file, vid_file, news_data = create_visual_content()
    
    if img_file and news_data:
        success = create_video(img_file, vid_file)
        if success:
            
            # --- השינוי כאן: שימוש בפונקציית Gemini ---
            generated_caption = generate_reel_description(
                title=news_data['title'],
                description=news_data['description']
            )
            
            caption = f"{generated_caption}\n\n#חדשות #עדכון {news_data['hashtags']}"
            # ----------------------------------------
            
            if CONFIG["UPLOAD_TO_INSTAGRAM"]:
                upload_to_instagram(vid_file, caption)
            else:
                print(f"\n[i] Done! Video saved as: {vid_file}")
                # הדפס את התיאור שג'מיני יצר
                print(f"[i] Generated Caption:\n{caption}")