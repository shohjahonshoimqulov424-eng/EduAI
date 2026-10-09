import os
import base64
import sqlite3
from datetime import date, datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, session
from groq import Groq

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-launch")

DB_PATH = os.environ.get("DB_PATH", "eduai.db")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
FREE_TRANSLATIONS_PER_DAY = 3

API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None

TEXT_MODEL = "openai/gpt-oss-20b"
IMAGE_MODEL = "qwen/qwen3.8-27b"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                user_id TEXT NOT NULL,
                usage_date TEXT NOT NULL,
                translations INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, usage_date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id TEXT PRIMARY KEY,
                plan TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
        """)

init_db()

PAGE = r"""
<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EduAI — Ta'lim uchun AI</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Arial,sans-serif;background:#f3f6fc;color:#172033}
header{background:#243b80;color:white;padding:20px;text-align:center}
header h1{margin:0 0 7px}
header p{margin:0;color:#dbe5ff}
main{max-width:850px;margin:25px auto;padding:15px}
.panel{background:white;padding:22px;border-radius:18px;box-shadow:0 5px 25px #182b5010;margin-bottom:16px}
#chat{min-height:280px;max-height:52vh;overflow:auto;margin-bottom:18px}
.msg{padding:13px 15px;border-radius:14px;margin:10px 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55}
.user{background:#e8efff;margin-left:12%}
.ai{background:#f0f3f8;margin-right:5%}
label{display:block;margin:12px 0 6px;font-weight:bold}
textarea,select,input[type=password]{width:100%;padding:13px;border:1px solid #ccd4e3;border-radius:12px;font:inherit}
textarea{min-height:105px;resize:vertical}
input[type=file]{width:100%;margin:8px 0}
button{border:0;border-radius:11px;padding:13px 18px;font-size:16px;cursor:pointer}
#send{background:#294bb1;color:white;width:100%;margin-top:10px}
#send:disabled{opacity:.6}
.small{font-size:13px;color:#68758a}
.prices{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.price{border:1px solid #dbe2ef;border-radius:12px;padding:15px}
.price strong{display:block;margin:7px 0;color:#294bb1;font-size:19px}
footer{text-align:center;padding:18px;color:#68758a}
</style>
</head>
<body>
<header>
<h1>🎓 EduAI</h1>
<p>Ta'lim uchun aqlli yordamchi</p>
</header>
<main>
<div class="panel">
<h2>AI bilan savol-javob</h2>
<p class="small">Tarjima uchun “Tarjima” rejimini tanlang. Kuniga 3 ta bepul tarjima beriladi.</p>
<div id="chat" aria-live="polite">
<div class="msg ai">Salom! Men EduAI yordamchisiman. Tarjima, matematika, insho va dars ishlanmalarida yordam beraman.</div>
</div>
<form id="form">
<label for="mode">Ish turi</label>
<select id="mode">
<option value="question">Savol-javob / masala yechish</option>
<option value="translation">Tarjima (kuniga 3 ta bepul)</option>
</select>
<label for="question">Savolingiz</label>
<textarea id="question" placeholder="Masalan: 2x + 5 = 15 tenglamani yech..." maxlength="15000"></textarea>
<label for="image">Rasm (ixtiyoriy)</label>
<input type="file" id="image" accept="image/png,image/jpeg,image/webp">
<p class="small">Rasm hajmi 7 MB dan oshmasin.</p>
<button id="send" type="submit">Yuborish</button>
</form>
</div>

<div class="panel">
<h2>EduAI tariflari</h2>
<div class="prices">
<div class="price">1 oy<strong>100 000 so'm</strong><span class="small">Obuna</span></div>
<div class="price">3 oy<strong>300 000 so'm</strong><span class="small">Obuna</span></div>
<div class="price">1 yil<strong>800 000 so'm</strong><span class="small">Obuna</span></div>
</div>
<p class="small">To'lov tizimi hali ulanmagan. Hozircha bu tariflar ma'lumot uchun ko'rsatilgan.</p>
</div>
</main>
<footer>© EduAI — ta'lim uchun AI yordamchi</footer>
<script>
const form = document.getElementById('form');
const question = document.getElementById('question');
const imageInput = document.getElementById('image');
const modeInput = document.getElementById('mode');
const chat = document.getElementById('chat');
const send = document.getElementById('send');

function addMessage(text, cls) {
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = question.value.trim();
  const file = imageInput.files[0];

  if (!message && !file) {
    addMessage('Savol yozing yoki rasm tanlang.', 'ai');
    return;
  }
  if (file && file.size > 7 * 1024 * 1024) {
    addMessage('Rasm hajmi 7 MB dan kichik bo‘lishi kerak.', 'ai');
    return;
  }

  addMessage(message || 'Rasmdagi topshiriqni yech.', 'user');
  send.disabled = true;
  send.textContent = 'Javob tayyorlanmoqda...';
  const loading = addMessage('Biroz kuting...', 'ai');

  try {
    const payload = {message, mode: modeInput.value};
    if (file) {
      payload.image = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Rasmni o‘qib bo‘lmadi.'));
        reader.readAsDataURL(file);
      });
    }

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    loading.remove();

    if (!response.ok) throw new Error(data.error || 'AI xatolik qaytardi.');
    addMessage(data.answer || 'Javob bo‘sh qaytdi.', 'ai');
    if (data.translations_left !== undefined) {
      addMessage('Bugun qolgan bepul tarjimalar: ' + data.translations_left, 'ai');
    }
    question.value = '';
    imageInput.value = '';
  } catch (error) {
    loading.textContent = 'Xato: ' + error.message;
  } finally {
    send.disabled = false;
    send.textContent = 'Yuborish';
  }
});
</script>
</body>
</html>
"""

ADMIN_PAGE = r"""
<!doctype html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EduAI admin</title>
<style>body{font-family:Arial;max-width:650px;margin:35px auto;padding:16px;background:#f3f6fc}
form,.box{background:white;padding:20px;border-radius:12px;margin:12px 0}
input,button{padding:12px;width:100%;box-sizing:border-box;margin-top:8px}
button{background:#294bb1;color:white;border:0;border-radius:8px}</style></head><body>
<h1>EduAI — Admin</h1>
<form method="post"><label>Admin kaliti</label>
<input type="password" name="key" required>
<button type="submit">Statistikani ko‘rish</button></form>
{% if stats %}
<div class="box"><p>Jami foydalanuvchilar: <b>{{ stats.users }}</b></p>
<p>Bugun faol tarjimonlar: <b>{{ stats.translators_today }}</b></p>
<p>Faol obunalar: <b>{{ stats.active_subscriptions }}</b></p></div>
{% endif %}
{% if error %}<p>{{ error }}</p>{% endif %}
</body></html>
"""

SYSTEM_PROMPT = """
Sen EduAI, o'quvchilar va o'qituvchilar uchun yordamchisan.
O'zbek, rus va ingliz tillarida javob ber.
Tarjima, matematika, fan masalalari, insho, reja,
dars ishlanmasi va testlar tuzishda yordam ber.
Masalalarni imkon qadar bosqichma-bosqich tushuntir.
Foydalanuvchi ishlatgan tilga mos javob qaytar.
Rasm yuborilsa, undagi matn va topshiriqni tahlil qil.
"""

def ensure_user():
    user_id = session.get("eduai_user_id")
    if not user_id:
        user_id = base64.urlsafe_b64encode(os.urandom(18)).decode("ascii").rstrip("=")
        session["eduai_user_id"] = user_id
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)",
            (user_id, datetime.utcnow().isoformat(timespec="seconds"))
        )
    return user_id

def active_subscription(user_id):
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_db() as conn:
        row = conn.execute(
            "SELECT plan FROM subscriptions WHERE user_id=? AND status='active' AND expires_at>?",
            (user_id, now)
        ).fetchone()
    return row["plan"] if row else None

def translations_used(user_id):
    today = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute(
            "SELECT translations FROM daily_usage WHERE user_id=? AND usage_date=?",
            (user_id, today)
        ).fetchone()
    return row["translations"] if row else 0

def use_translation(user_id):
    today = date.today().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO daily_usage (user_id, usage_date, translations)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, usage_date)
            DO UPDATE SET translations = translations + 1
        """, (user_id, today))
        row = conn.execute(
            "SELECT translations FROM daily_usage WHERE user_id=? AND usage_date=?",
            (user_id, today)
        ).fetchone()
    return row["translations"]

@app.route("/", methods=["GET"])
def home():
    ensure_user()
    return render_template_string(PAGE)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "EduAI"})

@app.route("/api/chat", methods=["POST"])
def chat():
    user_id = ensure_user()
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    image = data.get("image")
    mode = str(data.get("mode", "question")).strip().lower()
    is_translation = mode == "translation"

    if not message and not image:
        return jsonify({"error": "Savol yoki rasm yuboring."}), 400
    if len(message) > 15000:
        return jsonify({"error": "Matn 15 000 belgidan oshmasin."}), 400

    plan = active_subscription(user_id)
    used = translations_used(user_id) if is_translation else 0
    if is_translation and not plan and used >= FREE_TRANSLATIONS_PER_DAY:
        return jsonify({
            "error": "Bugungi 3 ta bepul tarjima limiti tugadi. Davom etish uchun obuna kerak."
        }), 429

    if client is None:
        return jsonify({"error": "GROQ_API_KEY Render Environment'da topilmadi."}), 500

    try:
        if image:
            if not isinstance(image, str) or "," not in image:
                return jsonify({"error": "Rasm formati noto'g'ri."}), 400
            header, encoded = image.split(",", 1)
            mime = header.removeprefix("data:").split(";")[0]
            if mime not in ("image/jpeg", "image/png", "image/webp"):
                return jsonify({"error": "JPEG, PNG yoki WEBP rasm yuboring."}), 400
            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception:
                return jsonify({"error": "Rasm ma'lumotini o'qib bo'lmadi."}), 400
            if len(raw) > 7 * 1024 * 1024:
                return jsonify({"error": "Rasm juda katta."}), 413

            prompt = message or "Rasmdagi topshiriqlarni o'qib, javoblarini bosqichma-bosqich tushuntir."
            result = client.chat.completions.create(
                model=IMAGE_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image}}
                    ]}
                ],
                max_completion_tokens=4000
            )
        else:
            prompt = message
            if is_translation:
                prompt = "Quyidagi matnni tarjima qil. Agar maqsad til ko'rsatilmagan bo'lsa, qaysi tilga tarjima kerakligini aniqlashtir. Matn:\n" + message
            result = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=4000
            )

        answer = result.choices[0].message.content or "Javob olinmadi."
        response_data = {"success": True, "answer": answer}
        if is_translation and not plan:
            now_used = use_translation(user_id)
            response_data["translations_left"] = max(0, FREE_TRANSLATIONS_PER_DAY - now_used)
        return jsonify(response_data)

    except Exception as exc:
        print("EduAI API xatosi:", repr(exc))
        return jsonify({
            "error": "AI javob bera olmadi. Render Logs va Groq API sozlamalarini tekshiring."
        }), 502

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "GET":
        return render_template_string(ADMIN_PAGE, stats=None, error=None)
    if not ADMIN_KEY:
        return render_template_string(ADMIN_PAGE, stats=None,
            error="Render Environment'da ADMIN_KEY sozlanmagan.")
    if request.form.get("key", "") != ADMIN_KEY:
        return render_template_string(ADMIN_PAGE, stats=None, error="Admin kaliti noto'g'ri."), 403

    today = date.today().isoformat()
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_db() as conn:
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        translators = conn.execute(
            "SELECT COUNT(DISTINCT user_id) AS n FROM daily_usage WHERE usage_date=? AND translations>0",
            (today,)
        ).fetchone()["n"]
        subs = conn.execute(
            "SELECT COUNT(*) AS n FROM subscriptions WHERE status='active' AND expires_at>?",
            (now,)
        ).fetchone()["n"]
    return render_template_string(ADMIN_PAGE,
        stats={"users": users, "translators_today": translators, "active_subscriptions": subs},
        error=None)

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({"error": "Yuborilgan ma'lumot juda katta."}), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
  
