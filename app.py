import os
import re
import json
import uuid
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
from werkzeug.utils import secure_filename
from groq import Groq

# ── App Config ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'heritagehub-digital-archive-2026')
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
DB_PATH = 'heritage.db'
ADMIN_PASSWORD = 'alhanshim'
LLM_MODEL = "Llama-3.1-8B-Instant"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Static Data ──────────────────────────────────────────────────────────────
CATEGORIES = [
    {'id': 'family_wisdom', 'en': 'Family Wisdom', 'ar': 'حكمة الأسرة'},
    {'id': 'traditions', 'en': 'Cultural Traditions', 'ar': 'التقاليد الثقافية'},
    {'id': 'life_lessons', 'en': 'Life Lessons', 'ar': 'دروس الحياة'},
    {'id': 'memories', 'en': 'Heritage Memories', 'ar': 'ذكريات التراث'},
    {'id': 'values', 'en': 'Values & Morals', 'ar': 'القيم والأخلاق'},
    {'id': 'ancestors', 'en': "Ancestors' Stories", 'ar': 'قصص الأجداد'},
]

UAE_VALUES = [
    'Respect',
    'Unity',
    'Responsibility',
    'Hard Work',
    'Compassion',
    'Loyalty',
    'Generosity',
    'Wisdom',
    'Family Bonds',
    'Hospitality',
    'Patience',
    'Courage',
]

UAE_VALUES_AR = {
    'Respect': 'الاحترام',
    'Unity': 'الوحدة',
    'Responsibility': 'المسؤولية',
    'Hard Work': 'العمل الجاد',
    'Compassion': 'التعاطف',
    'Loyalty': 'الولاء',
    'Generosity': 'الكرم',
    'Wisdom': 'الحكمة',
    'Family Bonds': 'الروابط الأسرية',
    'Hospitality': 'الضيافة',
    'Patience': 'الصبر',
    'Courage': 'الشجاعة',
}

RELATIONSHIPS = [
    'Grandmother',
    'Grandfather',
    'Mother',
    'Father',
    'Aunt',
    'Uncle',
    'Great-grandparent',
    'Elder Neighbor',
    'Other',
]

ARABIC_SCRIPT_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
FOREIGN_SCRIPT_RE = re.compile(r'[A-Za-z\u0400-\u04FF]')


# ── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                title_en TEXT NOT NULL,
                title_ar TEXT NOT NULL,
                content_en TEXT NOT NULL,
                content_ar TEXT NOT NULL,
                original_story TEXT DEFAULT '',
                original_language TEXT DEFAULT 'English',
                category TEXT NOT NULL DEFAULT 'memories',
                values_list TEXT DEFAULT '',
                storyteller_name TEXT DEFAULT '',
                storyteller_age INTEGER DEFAULT 0,
                relationship TEXT DEFAULT '',
                location TEXT DEFAULT 'UAE',
                theme TEXT DEFAULT '',
                image_path TEXT DEFAULT '',
                featured INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )'''
        )
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )'''
        )
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS page_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page TEXT NOT NULL,
                story_id TEXT,
                visitor_ip TEXT,
                visited_at TEXT NOT NULL
            )'''
        )
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                page TEXT DEFAULT 'general',
                submitted_at TEXT NOT NULL
            )'''
        )
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS unique_visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_ip TEXT NOT NULL,
                visit_date TEXT NOT NULL,
                first_page TEXT,
                UNIQUE(visitor_ip, visit_date)
            )'''
        )
        conn.commit()
    seed_stories()


def seed_stories():
    """Insert sample stories if archive is empty."""
    with get_db() as conn:
        if conn.execute('SELECT COUNT(*) FROM stories').fetchone()[0] > 0:
            return

        samples = [
            {
                'id': str(uuid.uuid4()),
                'title_en': 'The Date Palm and the Desert Rain',
                'title_ar': 'النخلة ومطر الصحراء',
                'content_en': (
                    'My grandfather would rise before dawn every morning and walk '
                    'to his date palm grove as the desert air still carried the cool '
                    'breath of night. He never hired workers for the harvest — he said '
                    'that the palms knew his hands, and the dates tasted sweeter for it. '
                    'One year a fierce haboob swept through and broke three of his oldest '
                    'trees. My father found him standing among the wreckage, smiling. '
                    "'A palm that survives the storm,' he said, 'gives the best fruit.' "
                    'He replanted that same week. Those trees still stand today, '
                    'taller than any in the village. We harvest them every Ramadan '
                    'as a family, and I taste in every date the patience of a man '
                    'who never surrendered to loss.'
                ),
                'content_ar': (
                    'كان جدي يستيقظ قبل الفجر كل صباح ويمشي إلى بستانه من النخيل '
                    'بينما كان هواء الصحراء لا يزال يحمل برودة الليل. لم يستعن بعمال '
                    'قط في موسم الحصاد، إذ كان يقول إن النخيل يعرف يديه والتمر يكون '
                    'أحلى بسببهما. في عام واحد اجتاحت عاصفة رملية عاتية وكسرت ثلاثاً '
                    'من أقدم نخيله. وجده أبي واقفاً وسط الدمار وهو يبتسم. قال '
                    '"النخلة التي تصمد أمام العاصفة تعطي أفضل الثمار." وأعاد الزراعة '
                    'في الأسبوع ذاته. تلك الأشجار لا تزال قائمة حتى اليوم، أطول '
                    'من أي نخلة في القرية. نحصدها كل رمضان كأسرة واحدة، وأجد في '
                    'كل تمرة طعم صبر رجل لم يستسلم للخسارة قط.'
                ),
                'original_story': 'Sample seeded story.',
                'original_language': 'English',
                'category': 'ancestors',
                'values_list': 'Patience,Hard Work,Family Bonds',
                'storyteller_name': 'Mohammed Al Mansoori',
                'storyteller_age': 82,
                'relationship': 'Grandfather',
                'location': 'Al Ain',
                'theme': 'Resilience through the desert storm',
                'image_path': '',
                'featured': 1,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            {
                'id': str(uuid.uuid4()),
                'title_en': 'The Majlis of Open Doors',
                'title_ar': 'مجلس الأبواب المفتوحة',
                'content_en': (
                    "My grandmother's house had a majlis that was never locked. "
                    'Neighbours, strangers, merchants passing through — all were '
                    'welcome. She kept a large pot of gahwa on the fire from morning '
                    'to evening, and her cardamom-spiced coffee became known across '
                    'three villages. Once a traveller arrived close to midnight, '
                    'exhausted and lost. She fed him, gave him a place to sleep, and '
                    'sent him off with enough food for two days. Years later, that '
                    'traveller returned as a successful merchant and brought gifts '
                    'for the entire community. My grandmother accepted only the gahwa '
                    'beans he brought, and she made coffee with them for the whole '
                    'neighbourhood. "Hospitality," she told me, "is never an expense. '
                    'It is the seed of something you cannot yet see."'
                ),
                'content_ar': (
                    'كان لبيت جدتي مجلس لم يُغلق بابه قط. الجيران والغرباء '
                    'والتجار العابرون — كلهم كانوا موضع ترحيب. كانت تحتفظ بدلة '
                    'كبيرة من القهوة على النار من الصباح حتى المساء، وذاعت شهرة '
                    'قهوتها المعطرة بالهيل في ثلاث قرى. ذات مرة وصل مسافر قرب '
                    'منتصف الليل منهكاً وضائعاً. أطعمته وأعطته مكاناً للنوم '
                    'وودّعته بما يكفيه من طعام ليومين. بعد سنوات عاد ذلك المسافر '
                    'تاجراً ناجحاً وأحضر هدايا لكامل المجتمع. قبلت جدتي فقط '
                    'حبوب القهوة التي أحضرها، وصنعت منها قهوة للحي كله. قالت لي '
                    '"الضيافة ليست نفقة أبداً. إنها بذرة لشيء لم ترَه بعد."'
                ),
                'original_story': 'Sample seeded story.',
                'original_language': 'English',
                'category': 'traditions',
                'values_list': 'Hospitality,Generosity,Compassion',
                'storyteller_name': 'Fatima Al Rashidi',
                'storyteller_age': 76,
                'relationship': 'Grandmother',
                'location': 'Abu Dhabi',
                'theme': 'The open door that changes lives',
                'image_path': '',
                'featured': 1,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            {
                'id': str(uuid.uuid4()),
                'title_en': 'Pearling Lessons from the Deep',
                'title_ar': 'دروس الغوص من الأعماق',
                'content_en': (
                    'Before oil, our family lived by the pearl. My great-grandfather '
                    'was a naham — a singer on the pearl dhow — whose voice kept the '
                    "divers' rhythm as they plunged into the Gulf's green depths. "
                    'He told my grandfather that the sea teaches three things no '
                    'school can: how to hold your breath when the world presses in, '
                    'how to trust the rope that connects you to those above, and how '
                    'to release what is not yours to keep. He dove for thirty years '
                    'and came up empty-handed many days. But he said an empty hand '
                    'and a full heart are wealth enough. I think of him when I face '
                    'my own pressures — the modern kind, the kind that feel like '
                    'deep water — and I remember that the pearl waits for the patient.'
                ),
                'content_ar': (
                    'قبل النفط، كانت أسرتنا تعيش على اللؤلؤ. كان جدّ جدي نهاماً '
                    '— مغنياً على سفينة الغوص — صوته يحفظ إيقاع الغواصين وهم '
                    'ينزلون إلى أعماق الخليج الخضراء. أخبر جدي أن البحر يعلّم '
                    'ثلاثة أشياء لا تستطيع أي مدرسة تعليمها: كيف تحبس أنفاسك '
                    'حين يضغط العالم عليك، وكيف تثق بالحبل الذي يربطك بمن هم '
                    'فوقك، وكيف تترك ما ليس لك أن تحتفظ به. غاص ثلاثين عاماً '
                    'وصعد خالي اليدين كثيراً من الأيام. لكنه قال إن اليد الفارغة '
                    'والقلب المليء ثروة كافية. أفكر فيه حين أواجه ضغوطي — '
                    'النوع الحديث، النوع الذي يشبه الغوص في الأعماق — '
                    'وأتذكر أن اللؤلؤة تنتظر الصبور.'
                ),
                'original_story': 'Sample seeded story.',
                'original_language': 'English',
                'category': 'ancestors',
                'values_list': 'Patience,Hard Work,Courage,Wisdom',
                'storyteller_name': 'Khalid Al Hameli',
                'storyteller_age': 71,
                'relationship': 'Grandfather',
                'location': 'Dubai',
                'theme': "The pearl diver's wisdom from the sea",
                'image_path': '',
                'featured': 1,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
        ]

        for s in samples:
            conn.execute(
                '''INSERT INTO stories (
                    id, title_en, title_ar, content_en, content_ar, original_story,
                    original_language, category, values_list, storyteller_name,
                    storyteller_age, relationship, location, theme, image_path,
                    featured, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    s['id'],
                    s['title_en'],
                    s['title_ar'],
                    s['content_en'],
                    s['content_ar'],
                    s['original_story'],
                    s['original_language'],
                    s['category'],
                    s['values_list'],
                    s['storyteller_name'],
                    s['storyteller_age'],
                    s['relationship'],
                    s['location'],
                    s['theme'],
                    s['image_path'],
                    s['featured'],
                    s['created_at'],
                ),
            )
        conn.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_text(text):
    if not text:
        return ''
    text = text.replace('\ufeff', '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def has_foreign_chars(text):
    if not text:
        return False
    return bool(FOREIGN_SCRIPT_RE.search(text))


def looks_like_arabic(text):
    if not text:
        return False
    return bool(ARABIC_SCRIPT_RE.search(text))


def get_setting(key, default=''):
    with get_db() as conn:
        row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    with get_db() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (key, value),
        )
        conn.commit()


def get_client_ip():
    """Get client IP address from request (handles proxies)."""
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    return ip


def track_page_visit(page, story_id=None):
    """Record a page visit for analytics and count unique visitor per day."""
    visitor_ip = get_client_ip()
    today = datetime.now().strftime('%Y-%m-%d')
    
    with get_db() as conn:
        # Record the page visit for detailed analytics
        conn.execute(
            'INSERT INTO page_visits (page, story_id, visitor_ip, visited_at) VALUES (?, ?, ?, ?)',
            (page, story_id, visitor_ip, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        )
        
        # Count unique visitor only once per day
        try:
            conn.execute(
                'INSERT INTO unique_visitors (visitor_ip, visit_date, first_page) VALUES (?, ?, ?)',
                (visitor_ip, today, page),
            )
        except sqlite3.IntegrityError:
            # This IP was already counted today, so skip
            pass
        
        conn.commit()


def get_analytics():
    """Fetch analytics data: visitors by page and top stories read."""
    with get_db() as conn:
        # Total visits by page
        page_stats = conn.execute('''
            SELECT page, COUNT(*) as count
            FROM page_visits
            GROUP BY page
            ORDER BY count DESC
        ''').fetchall()
        
        # Top 10 stories read
        top_stories = conn.execute('''
            SELECT 
                s.id, 
                s.title_en, 
                COUNT(pv.id) as read_count
            FROM page_visits pv
            JOIN stories s ON s.id = pv.story_id
            WHERE pv.story_id IS NOT NULL
            GROUP BY pv.story_id
            ORDER BY read_count DESC
            LIMIT 10
        ''').fetchall()
        
        # Total page visits (for detailed analytics)
        total_visits = conn.execute('SELECT COUNT(*) FROM page_visits').fetchone()[0]
        
        # Unique visitors (counted once per day per IP from unique_visitors table)
        unique_visitors = conn.execute(
            'SELECT COUNT(*) FROM unique_visitors'
        ).fetchone()[0]
    
    return {
        'page_stats': page_stats,
        'top_stories': top_stories,
        'total_visits': total_visits,
        'unique_visitors': unique_visitors
    }


def get_all_feedback():
    """Fetch all feedback submissions."""
    with get_db() as conn:
        feedback = conn.execute('''
            SELECT id, email, message, page, submitted_at
            FROM feedback
            ORDER BY submitted_at DESC
        ''').fetchall()
    return feedback


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated


def call_llama(api_key, system_prompt, user_prompt, temperature=0.5, require_json=False):
    """Call Llama 3.1 via Groq and return the text response."""
    if not api_key:
        return 'ERROR: No API key configured.'

    try:
        client = Groq(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': user_prompt})

        kwargs = {
            'model': LLM_MODEL,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': 3000,
        }
        if require_json:
            kwargs['response_format'] = {'type': 'json_object'}

        completion = client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f'ERROR: {str(e)}'


def _parse_json_response(raw):
    """Strip markdown fences and parse JSON."""
    clean = raw.strip()
    if clean.startswith('```json'):
        clean = clean[7:]
    if clean.startswith('```'):
        clean = clean[3:]
    if clean.endswith('```'):
        clean = clean[:-3]
    clean = clean.strip()
    return json.loads(clean)


def _repair_arabic_fields(api_key, data, fields_to_fix):
    repair_system = (
        'You are a strict Arabic editor and bilingual heritage proofreader. '
        'Rewrite only the specified Arabic fields in pure Modern Standard Arabic. '
        'Remove every Latin or Cyrillic character. Preserve meaning exactly. '
        'Do not add new events. Return JSON only.'
    )
    payload = json.dumps(data, ensure_ascii=False)
    repair_user = f'''
Fix only these fields in the JSON: {', '.join(fields_to_fix)}.
Keep all other fields unchanged.

Rules:
- Arabic must be pure Modern Standard Arabic.
- No English letters.
- No Cyrillic letters.
- No mixed-script words.
- No transliteration.
- Keep the story faithful to the original.

JSON:
{payload}
'''.strip()
    repaired_raw = call_llama(api_key, repair_system, repair_user, temperature=0.1, require_json=True)
    if repaired_raw.startswith('ERROR'):
        return None, repaired_raw
    try:
        repaired = _parse_json_response(repaired_raw)
        for field in fields_to_fix:
            repaired[field] = normalize_text(repaired.get(field, ''))
        return repaired, None
    except json.JSONDecodeError:
        return None, f'AI returned invalid repaired JSON. Raw: {repaired_raw[:200]}'


def ai_process_story(api_key, story, language, values, storyteller):
    """Polish and translate an existing raw story into EN + AR + theme."""
    vals_str = ', '.join(values) if values else 'UAE family values'
    system = (
        'You are a master heritage archivist, cultural editor, literary translator, and storyteller '
        'specializing in Emirati family narratives. Your expertise spans Islamic values, UAE customs, '
        'and child-friendly storytelling. '
        'Your job is to take a raw story submitted by a user and produce a polished '
        'bilingual version of THAT SAME STORY — do NOT invent new plot points or change the core narrative. '
        'You must output valid JSON ONLY. No markdown, no extra text. '
        'The Arabic fields must be pure Modern Standard Arabic with zero Latin letters, '
        'zero Cyrillic letters, zero mixed-script words, and zero transliteration.'
    )
    user = f'''
You have received the following raw story written in {language}.
Storyteller context: {storyteller or 'Emirati elder'}
UAE Values to highlight: {vals_str}

--- RAW STORY ---
{story}
--- END OF STORY ---

Your task:
1. Polish and rewrite the story in fluent literary English as `content_en`.
2. Translate the story into pure Modern Standard Arabic as `content_ar`.
3. Create a short evocative English title as `title_en`.
4. Create a short beautiful Arabic title as `title_ar`.
5. Identify the central theme in 5-10 words as `theme`.

QUALITY & AUTHENTICITY REQUIREMENTS:
- The story must be CHILD-SAFE: appropriate for readers aged 5-18, with no violence, adult themes, or disturbing content.
- The story must reflect ISLAMIC & EMIRATI VALUES: kindness, respect, family, honesty, patience, compassion, and duty.
- The narrative must be LOGICALLY COHERENT: clear cause-and-effect, believable character motivations, and satisfying resolution.
- The story should FEATURE AUTHENTIC EMIRATI SETTINGS & CUSTOMS: references to daily life, traditions, geography, or cultural practices.
- Avoid FANTASY ELEMENTS unless they are clearly fairy-tale framing (e.g., "once upon a time").
- The English version should be LITERARY & VIVID: use sensory details, show-don't-tell, and create emotional resonance.
- The Arabic must be ELEGANT, NATURAL & DEEPLY CULTURAL: use idioms, classical references where appropriate, and maintain the warmth of oral storytelling.

CRITICAL LANGUAGE RULES:
- `title_ar` and `content_ar` MUST contain ONLY Arabic script and Arabic punctuation.
- Do NOT include any English letters, Cyrillic letters, foreign names in Latin script, or mixed-script words.
- Do NOT leave any foreign word untranslated inside the Arabic text (translate place names, character names, and concepts).
- Do NOT merge Arabic with foreign words using transliteration (e.g., never write "al-family" in Arabic).
- Do NOT invent new plot points or change the core narrative.
- Keep the meaning FAITHFUL to the original story.

Return EXACTLY this JSON and nothing else:
{{
  "title_en": "Evocative English title",
  "title_ar": "عنوان عربي جميل",
  "content_en": "Complete polished story in English",
  "content_ar": "قصة كاملة بالعربية الفصحى النقية",
  "theme": "Central theme in 5-10 words"
}}
'''.strip()

    raw = call_llama(api_key, system, user, temperature=0.25, require_json=True)
    if raw.startswith('ERROR'):
        return None, raw

    try:
        data = _parse_json_response(raw)
    except json.JSONDecodeError:
        return None, f'AI returned invalid JSON. Raw: {raw[:200]}'

    data['title_ar'] = normalize_text(data.get('title_ar', ''))
    data['content_ar'] = normalize_text(data.get('content_ar', ''))

    if has_foreign_chars(data.get('title_ar', '')) or has_foreign_chars(data.get('content_ar', '')):
        repaired, repair_err = _repair_arabic_fields(api_key, data, ['title_ar', 'content_ar'])
        if repair_err:
            return None, repair_err
        data = repaired

    return data, None


def ai_generate_story(api_key, topic, category, values, language, storyteller_context):
    """AI-generate a complete new heritage story."""
    vals_str = ', '.join(values) if values else 'UAE family values'
    cat_label = next((c['en'] for c in CATEGORIES if c['id'] == category), category)
    system = (
        'You are a celebrated Emirati author, historian of daily life, cultural diplomat, and master storyteller. '
        'You create authentic, emotionally rich family heritage stories that feel lived, specific, true to Emirati memory, '
        'and rooted in Islamic and UAE cultural values. Your stories are suitable for all ages and embody wisdom, kindness, and tradition. '
        'You must respond ONLY with valid JSON. No markdown fences. No commentary. '
        'The Arabic fields must be pure Modern Standard Arabic with no foreign letters or mixed scripts.'
    )
    user = f'''
Write an original, authentic UAE family heritage story for the digital archive.

Story Topic Seed: {topic}
Category: {cat_label}
UAE Values to embody: {vals_str}
Language Preference: {language}
Storyteller Context: {storyteller_context or 'An Emirati elder'}

Write the story as if it were a genuine remembered moment from an elder's life — grounded in real Emirati experience,
not fantasy. Every detail should feel authentic and specific to UAE heritage.

REQUIRED STORY STRUCTURE:
1. TIME: Clearly define the time period (past era, season, or occasion like Ramadan, Eid, harvest time).
2. PLACE: Describe a specific real Emirati location (village, city, desert, oasis, sea, family home, majlis, marketplace).
3. CHARACTERS: Give each character a real role and believable relationships. Use authentic Emirati names.
4. OPENING: Begin with a vivid, engaging scene that draws readers in emotionally.
5. DEVELOPMENT: Build events naturally with clear cause-and-effect. Avoid sudden, unexplained plot shifts.
6. TURNING POINT: Include a meaningful moment or decision that changes the character's perspective or understanding.
7. ENDING: Close with a satisfying conclusion that feels earned, not forced.
8. LESSON: Weave in a clear moral or life lesson through actions and events, not explicit preaching.

CONTENT & QUALITY STANDARDS:
✓ MUST be CHILD-SAFE and AGE-APPROPRIATE: suitable for readers 5-18 years old.
✓ MUST embody ISLAMIC VALUES: compassion, honesty, respect, patience, generosity, family loyalty, duty to others.
✓ MUST be CULTURALLY AUTHENTIC: grounded in real Emirati life, traditions, geography, and daily customs.
✓ MUST have LOGICAL NARRATIVE: believable character motivations, realistic cause-and-effect, sensible resolution.
✓ MUST feature AUTHENTIC SETTINGS: majlis, desert, oasis, sea, date palm grove, gahwa ceremony, Ramadan, Eid, pearl diving,
  falconry, family gathering, henna, wedding customs, market, camel herding, fishing, agriculture, weaving.
✓ The English version should be LITERARY & VIVID: use sensory language (sights, sounds, tastes, textures, emotions).
✓ Avoid FANTASY unless clearly framed as folk-tale (e.g., "In the old days, they say...").
✓ The Arabic version must be WARM, NATURAL & ELOQUENT: use phrases that sound like authentic storytelling,
  incorporate classical Arabic idioms where fitting, and capture the heart of oral tradition.
✓ Show values through ACTIONS & DIALOGUE, not exposition.

LENGTH TARGETS:
- English: 300-450 words, engaging and literary.
- Arabic: 450-650 words, richly detailed and deeply cultural.

Return EXACTLY this JSON:
{{
  "title_en": "Evocative English title (4-8 words)",
  "title_ar": "عنوان عربي موجز وجميل",
  "content_en": "Complete story in English",
  "content_ar": "Complete story in Arabic",
  "theme": "Central theme in 5-10 words",
  "storyteller_name": "Authentic Emirati name",
  "location": "UAE city or region"
}}
'''.strip()

    raw = call_llama(api_key, system, user, temperature=0.35, require_json=True)
    if raw.startswith('ERROR'):
        return None, raw

    try:
        data = _parse_json_response(raw)
    except json.JSONDecodeError:
        return None, f'AI returned invalid JSON. Raw: {raw[:200]}'

    data['title_ar'] = normalize_text(data.get('title_ar', ''))
    data['content_ar'] = normalize_text(data.get('content_ar', ''))

    if has_foreign_chars(data.get('title_ar', '')) or has_foreign_chars(data.get('content_ar', '')):
        repaired, repair_err = _repair_arabic_fields(api_key, data, ['title_ar', 'content_ar'])
        if repair_err:
            return None, repair_err
        data = repaired

    return data, None


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        pwd = request.form.get('password', '').strip()
        if pwd == ADMIN_PASSWORD:
            session['admin'] = True
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Incorrect password. Please try again.'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('index'))


@app.route('/')
def index():
    track_page_visit('homepage')
    with get_db() as conn:
        featured = conn.execute(
            'SELECT * FROM stories WHERE featured = 1 ORDER BY created_at DESC LIMIT 3'
        ).fetchall()
        recent = conn.execute(
            'SELECT * FROM stories ORDER BY created_at DESC LIMIT 6'
        ).fetchall()
        total = conn.execute('SELECT COUNT(*) FROM stories').fetchone()[0]

        cat_counts = {}
        for cat in CATEGORIES:
            n = conn.execute(
                'SELECT COUNT(*) FROM stories WHERE category = ?',
                (cat['id'],),
            ).fetchone()[0]
            cat_counts[cat['id']] = n

    return render_template(
        'index.html',
        featured=featured,
        recent=recent,
        total=total,
        categories=CATEGORIES,
        cat_counts=cat_counts,
        admin=session.get('admin'),
    )


@app.route('/stories')
def stories():
    track_page_visit('archive')
    cat = request.args.get('category', '')
    val = request.args.get('value', '')
    lang = request.args.get('lang', '')
    q = request.args.get('q', '')

    with get_db() as conn:
        sql = 'SELECT * FROM stories WHERE 1=1'
        params = []

        if cat:
            sql += ' AND category = ?'
            params.append(cat)
        if val:
            sql += ' AND values_list LIKE ?'
            params.append(f'%{val}%')
        if lang:
            sql += ' AND original_language = ?'
            params.append(lang)
        if q:
            sql += ' AND (title_en LIKE ? OR title_ar LIKE ? OR content_en LIKE ? OR storyteller_name LIKE ?)'
            params.extend([f'%{q}%'] * 4)

        sql += ' ORDER BY created_at DESC'
        all_stories = conn.execute(sql, params).fetchall()

    return render_template(
        'stories.html',
        stories=all_stories,
        categories=CATEGORIES,
        uae_values=UAE_VALUES,
        selected_cat=cat,
        selected_val=val,
        selected_lang=lang,
        q=q,
        admin=session.get('admin'),
    )


@app.route('/story/<story_id>')
def story_detail(story_id):
    with get_db() as conn:
        s = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()

    if not s:
        return redirect(url_for('stories'))

    track_page_visit('story', story_id)
    
    values_list = [v.strip() for v in s['values_list'].split(',') if v.strip()] if s['values_list'] else []
    cat_label = next((c for c in CATEGORIES if c['id'] == s['category']), CATEGORIES[0])
    return render_template(
        'story.html',
        story=s,
        values_list=values_list,
        cat_label=cat_label,
        admin=session.get('admin'),
        categories=CATEGORIES,
    )


# ── API AI Chat ──────────────────────────────────────────────────────────────
@app.route('/api/chat/<story_id>', methods=['POST'])
def api_chat(story_id):
    with get_db() as conn:
        s = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()

    if not s:
        return jsonify({'error': 'Story not found'}), 404

    data = request.get_json(silent=True) or {}
    user_msg = data.get('message', '').strip()
    history = data.get('history', [])
    if not isinstance(history, list):
        history = []
    api_key = get_setting('gemini_api_key')

    if not user_msg:
        return jsonify({'error': 'Empty message'}), 400

    story_summary = (s['content_en'] or '')[:600]
    system_prompt = f'''
You are a knowledgeable and warm cultural guide discussing the family heritage story titled "{s['title_en']}" from the UAE Heritage Archive.

Story Summary:
{story_summary}

Storyteller: {s['storyteller_name']}, {s['relationship']}, from {s['location']}
Values: {s['values_list']}
Theme: {s['theme']}

YOUR RULES
1. ONLY discuss topics directly related to this story, its themes, the UAE values it embodies, or the Emirati cultural context it describes.
2. If asked something completely unrelated to this story or UAE culture, politely redirect: "I can only discuss topics related to this story and its cultural context."
3. Be warm, educational, and thoughtful — like a wise cultural guide.
4. Answers should be 2-4 paragraphs. Use examples from the story when relevant.
5. You may answer in English or Arabic depending on the user's language.
6. Never discuss politics, conflicts, or controversial topics.
'''.strip()

    history_text = ''
    for h in history[-6:]:
        role_label = 'User' if h.get('role') == 'user' else 'Assistant'
        history_text += f"{role_label}: {h.get('content', '')}\n"

    full_prompt = f'''{history_text}
User: {user_msg}'''.strip()

    reply = call_llama(api_key, system_prompt, full_prompt, temperature=0.5)
    return jsonify({'reply': reply})


# ── AI Generate Page ──────────────────────────────────────────────────────────
@app.route('/generate', methods=['GET', 'POST'])
@require_admin
def generate_story():
    api_key = get_setting('gemini_api_key')
    result = None
    error = None

    if request.method == 'POST':
        topic = request.form.get('topic', '').strip()
        category = request.form.get('category', 'memories')
        values = request.form.getlist('values')
        language = request.form.get('language', 'English')
        context = request.form.get('storyteller_context', '').strip()

        if not topic:
            error = 'Please provide a story topic or seed.'
        elif not api_key:
            error = 'Gemini API key not set. Go to Admin Settings.'
        else:
            result, error = ai_generate_story(api_key, topic, category, values, language, context)
            if result:
                if request.form.get('auto_save'):
                    sid = str(uuid.uuid4())
                    with get_db() as conn:
                        conn.execute(
                            '''INSERT INTO stories (
                                id, title_en, title_ar, content_en, content_ar,
                                original_story, original_language, category, values_list,
                                storyteller_name, storyteller_age, relationship, location,
                                theme, image_path, featured, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (
                                sid,
                                result.get('title_en', ''),
                                result.get('title_ar', ''),
                                result.get('content_en', ''),
                                result.get('content_ar', ''),
                                topic,
                                language,
                                category,
                                ','.join(values),
                                result.get('storyteller_name', 'AI Generated'),
                                0,
                                'AI Generated',
                                result.get('location', 'UAE'),
                                result.get('theme', ''),
                                '',
                                0,
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            ),
                        )
                        conn.commit()
                    flash('Story generated and saved to archive!', 'success')
                    return redirect(url_for('story_detail', story_id=sid))

    return render_template(
        'generate.html',
        categories=CATEGORIES,
        uae_values=UAE_VALUES,
        result=result,
        error=error,
        api_key=api_key,
        admin=True,
    )


# ── Admin Routes ──────────────────────────────────────────────────────────────
@app.route('/admin')
@require_admin
def admin_dashboard():
    with get_db() as conn:
        all_stories = conn.execute('SELECT * FROM stories ORDER BY created_at DESC').fetchall()
        total = len(all_stories)

        cat_counts = {}
        for cat in CATEGORIES:
            n = conn.execute('SELECT COUNT(*) FROM stories WHERE category = ?', (cat['id'],)).fetchone()[0]
            cat_counts[cat['id']] = n

    api_key = get_setting('gemini_api_key')
    analytics = get_analytics()
    all_feedback = get_all_feedback()
    
    return render_template(
        'admin/dashboard.html',
        stories=all_stories,
        total=total,
        categories=CATEGORIES,
        cat_counts=cat_counts,
        api_key=api_key,
        analytics=analytics,
        feedback=all_feedback,
        admin=True,
    )


@app.route('/admin/settings', methods=['POST'])
@require_admin
def admin_settings():
    key = request.form.get('gemini_api_key', '').strip()
    if key:
        set_setting('gemini_api_key', key)
        flash('API key saved.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/add', methods=['GET', 'POST'])
@require_admin
def admin_add():
    api_key = get_setting('gemini_api_key')
    error = None

    if request.method == 'POST':
        title_en = request.form.get('title_en', '').strip()
        title_ar = request.form.get('title_ar', '').strip()
        content_en = request.form.get('content_en', '').strip()
        content_ar = request.form.get('content_ar', '').strip()
        orig_story = request.form.get('original_story', '').strip()
        orig_lang = request.form.get('original_language', 'English')
        category = request.form.get('category', 'memories')
        values = request.form.getlist('values')
        sname = request.form.get('storyteller_name', '').strip()
        sage = int(request.form.get('storyteller_age', 0) or 0)
        rel = request.form.get('relationship', '')
        loc = request.form.get('location', 'UAE').strip()
        theme = request.form.get('theme', '').strip()
        featured = 1 if request.form.get('featured') else 0
        use_ai = request.form.get('use_ai')

        if not title_en or not content_en:
            error = 'Title and content (English) are required.'
        else:
            if use_ai and orig_story and api_key:
                ai_data, ai_err = ai_process_story(api_key, orig_story, orig_lang, values, sname)
                if ai_data:
                    if not title_ar:
                        title_ar = ai_data.get('title_ar', '')
                    if not content_ar:
                        content_ar = ai_data.get('content_ar', '')
                    if not theme:
                        theme = ai_data.get('theme', '')
                elif ai_err:
                    error = f'AI error: {ai_err}'

            if not error:
                if has_foreign_chars(title_ar) or has_foreign_chars(content_ar):
                    error = 'الترجمة العربية لم تخرج بصياغة سليمة. أعد المحاولة.'
                else:
                    image_path = ''
                    if 'image' in request.files:
                        f = request.files['image']
                        if f and f.filename and allowed_file(f.filename):
                            fn = secure_filename(f'{uuid.uuid4()}_{f.filename}')
                            f.save(os.path.join(UPLOAD_FOLDER, fn))
                            image_path = fn

                    sid = str(uuid.uuid4())
                    with get_db() as conn:
                        conn.execute(
                            '''INSERT INTO stories (
                                id, title_en, title_ar, content_en, content_ar,
                                original_story, original_language, category, values_list,
                                storyteller_name, storyteller_age, relationship, location,
                                theme, image_path, featured, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (
                                sid,
                                title_en,
                                title_ar,
                                content_en,
                                content_ar,
                                orig_story,
                                orig_lang,
                                category,
                                ','.join(values),
                                sname,
                                sage,
                                rel,
                                loc,
                                theme,
                                image_path,
                                featured,
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            ),
                        )
                        conn.commit()
                    flash('Story added to the archive.', 'success')
                    return redirect(url_for('admin_dashboard'))

    return render_template(
        'admin/story_form.html',
        action='add',
        story=None,
        categories=CATEGORIES,
        uae_values=UAE_VALUES,
        relationships=RELATIONSHIPS,
        error=error,
        api_key=api_key,
        admin=True,
    )


@app.route('/admin/edit/<story_id>', methods=['GET', 'POST'])
@require_admin
def admin_edit(story_id):
    api_key = get_setting('gemini_api_key')
    with get_db() as conn:
        s = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()

    if not s:
        return redirect(url_for('admin_dashboard'))

    error = None

    if request.method == 'POST':
        title_en = request.form.get('title_en', '').strip()
        title_ar = request.form.get('title_ar', '').strip()
        content_en = request.form.get('content_en', '').strip()
        content_ar = request.form.get('content_ar', '').strip()
        orig_story = request.form.get('original_story', '').strip()
        orig_lang = request.form.get('original_language', 'English')
        category = request.form.get('category', 'memories')
        values = request.form.getlist('values')
        sname = request.form.get('storyteller_name', '').strip()
        sage = int(request.form.get('storyteller_age', 0) or 0)
        rel = request.form.get('relationship', '')
        loc = request.form.get('location', 'UAE').strip()
        theme = request.form.get('theme', '').strip()
        featured = 1 if request.form.get('featured') else 0
        image_path = s['image_path'] or ''

        if 'image' in request.files:
            f = request.files['image']
            if f and f.filename and allowed_file(f.filename):
                fn = secure_filename(f'{uuid.uuid4()}_{f.filename}')
                f.save(os.path.join(UPLOAD_FOLDER, fn))
                image_path = fn

        if not title_en or not content_en:
            error = 'Title and content (English) are required.'
        else:
            if has_foreign_chars(title_ar) or has_foreign_chars(content_ar):
                error = 'الترجمة العربية لم تخرج بصياغة سليمة. أعد المحاولة.'
            else:
                with get_db() as conn:
                    conn.execute(
                        '''UPDATE stories SET
                            title_en = ?,
                            title_ar = ?,
                            content_en = ?,
                            content_ar = ?,
                            original_story = ?,
                            original_language = ?,
                            category = ?,
                            values_list = ?,
                            storyteller_name = ?,
                            storyteller_age = ?,
                            relationship = ?,
                            location = ?,
                            theme = ?,
                            image_path = ?,
                            featured = ?
                        WHERE id = ?''',
                        (
                            title_en,
                            title_ar,
                            content_en,
                            content_ar,
                            orig_story,
                            orig_lang,
                            category,
                            ','.join(values),
                            sname,
                            sage,
                            rel,
                            loc,
                            theme,
                            image_path,
                            featured,
                            story_id,
                        ),
                    )
                    conn.commit()

                flash('Story updated.', 'success')
                return redirect(url_for('admin_dashboard'))

    story_values = [v.strip() for v in s['values_list'].split(',') if v.strip()] if s['values_list'] else []
    return render_template(
        'admin/story_form.html',
        action='edit',
        story=s,
        story_values=story_values,
        categories=CATEGORIES,
        uae_values=UAE_VALUES,
        relationships=RELATIONSHIPS,
        error=error,
        api_key=api_key,
        admin=True,
    )


@app.route('/admin/delete/<story_id>', methods=['POST'])
@require_admin
def admin_delete(story_id):
    with get_db() as conn:
        conn.execute('DELETE FROM stories WHERE id = ?', (story_id,))
        conn.commit()
    flash('Story removed from archive.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/toggle-featured/<story_id>', methods=['POST'])
@require_admin
def toggle_featured(story_id):
    with get_db() as conn:
        s = conn.execute('SELECT featured FROM stories WHERE id = ?', (story_id,)).fetchone()
        if s:
            conn.execute(
                'UPDATE stories SET featured = ? WHERE id = ?',
                (0 if s['featured'] else 1, story_id),
            )
            conn.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback."""
    email = request.form.get('feedback_email', '').strip()
    message = request.form.get('feedback_message', '').strip()
    page = request.form.get('feedback_page', 'general').strip()
    
    if not email or not message:
        flash('Please provide both email and message.', 'error')
        return redirect(request.referrer or url_for('index'))
    
    with get_db() as conn:
        conn.execute(
            'INSERT INTO feedback (email, message, page, submitted_at) VALUES (?, ?, ?, ?)',
            (email, message, page, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        )
        conn.commit()
    
    flash('Thank you! Your feedback has been received.', 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/admin/delete-feedback/<int:feedback_id>', methods=['POST'])
@require_admin
def delete_feedback(feedback_id):
    """Delete feedback by ID."""
    with get_db() as conn:
        conn.execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))
        conn.commit()
    
    flash('Feedback deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)