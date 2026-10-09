import os
import base64
from flask import Flask, request, jsonify, render_template_string
from groq import Groq

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None

TEXT_MODEL = "openai/gpt-oss-20b"
IMAGE_MODEL = "qwen/qwen3.8-27b"

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
.panel{background:white;padding:22px;border-radius:18px;box-shadow:0 5px 25px #182b5010}
#chat{min-height:280px;max-height:52vh;overflow:auto;margin-bottom:18px}
.msg{padding:13px 15px;border-radius:14px;margin:10px 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55}
.user{background:#e8efff;margin-left:12%}
.ai{background:#f0f3f8;margin-right:5%}
label{display:block;margin:12px 0 6px;font-weight:bold}
textarea{width:100%;min-height:105px;resize:vertical;padding:13px;border:1px solid #ccd4e3;border-radius:12px;font:inherit}
input[type=file]{width:100%;margin:8px 0}
button{border:0;border-radius:11px;padding:13px 18px;font-size:16px;cursor:pointer}
#send{background:#294bb1;color:white;width:100%;margin-top:10px}
#send:disabled{opacity:.6}
.small{font-size:13px;color:#68758a}
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
<p class="small">Savol yozing yoki masala rasmini yuboring.</p>
<div id="chat" aria-live="polite">
<div class="msg ai">Salom! Men EduAI yordamchisiman. Tarjima, matematika, insho va dars ishlanmalarida yordam beraman.</div>
</div>
<form id="form">
<label for="question">Savolingiz</label>
<textarea id="question" placeholder="Masalan: 2x + 5 = 15 tenglamani yech..." maxlength="15000"></textarea>
<label for="image">Rasm (ixtiyoriy)</label>
<input type="file" id="image" accept="image/png,image/jpeg,image/webp">
<p class="small">Rasm hajmi 7 MB dan oshmasin.</p>
<button id="send" type="submit">Yuborish</button>
</form>
</div>
</main>
<footer>© EduAI — ta'lim uchun AI yordamchi</footer>
<script>
const form = document.getElementById('form');
const question = document.getElementById('question');
const imageInput = document.getElementById('image');
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
    const payload = {message};

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

    if (!response.ok) {
      throw new Error(data.error || 'AI xatolik qaytardi.');
    }

    addMessage(data.answer || 'Javob bo‘sh qaytdi.', 'ai');
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

SYSTEM_PROMPT = """
Sen EduAI, o'quvchilar va o'qituvchilar uchun yordamchisan.
O'zbek, rus va ingliz tillarida javob ber.
Tarjima, matematika, fan masalalari, insho, reja,
dars ishlanmasi va testlar tuzishda yordam ber.
Masalalarni imkon qadar bosqichma-bosqich tushuntir.
Foydalanuvchi ishlatgan tilga mos javob qaytar.
Rasm yuborilsa, undagi matn va topshiriqni tahlil qil.
"""

@app.route("/", methods=["GET"])
def home():
    return render_template_string(PAGE)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "EduAI"})

@app.route("/api/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify({
            "error": "GROQ_API_KEY Render Environment'da topilmadi."
        }), 500

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    image = data.get("image")

    if not message and not image:
        return jsonify({"error": "Savol yoki rasm yuboring."}), 400

    try:
        if image:
            if not isinstance(image, str) or "," not in image:
                return jsonify({"error": "Rasm formati noto'g'ri."}), 400

            header, encoded = image.split(",", 1)
            mime = header.removeprefix("data:").split(";")[0]

            if mime not in ("image/jpeg", "image/png", "image/webp"):
                return jsonify({
                    "error": "JPEG, PNG yoki WEBP rasm yuboring."
                }), 400

            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 7 * 1024 * 1024:
                return jsonify({"error": "Rasm juda katta."}), 413

            prompt = message or (
                "Rasmdagi topshiriqlarni o'qib, javoblarini "
                "bosqichma-bosqich tushuntir."
            )

            result = client.chat.completions.create(
                model=IMAGE_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": image
                        }}
                    ]}
                ],
                max_completion_tokens=4000
            )
        else:
            result = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message}
                ],
                max_completion_tokens=4000
            )

        answer = result.choices[0].message.content or "Javob olinmadi."
        return jsonify({"success": True, "answer": answer})

    except Exception as exc:
        print("EduAI API xatosi:", repr(exc))
        return jsonify({
            "error": "AI javob bera olmadi. Render Logs va Groq API sozlamalarini tekshiring."
        }), 502

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({"error": "Yuborilgan ma'lumot juda katta."}), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
    
