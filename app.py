import os
import base64
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

API_KEY = os.environ.get("GROQ_API_KEY")

if not API_KEY:
    raise RuntimeError("GROQ_API_KEY Render Environment'da topilmadi")

client = Groq(api_key=API_KEY)

TEXT_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = "qwen/qwen3.8-27b"

SYSTEM_PROMPT = """
Sen EduAI — o'qituvchilar va o'quvchilar uchun AI yordamchisan.

Vazifalaring:
1. O'zbek, rus va ingliz tillarida savollarga javob ber.
2. Matnlarni ruscha, inglizcha va o'zbekchaga tarjima qil.
3. Matematika va boshqa fanlardan misol va masalalarni yech.
4. Javoblarni tushunarli, bosqichma-bosqich izohla.
5. Insho, reja, dars ishlanmasi va testlar tuz.
6. Rasm yuborilsa, undagi matn, savol va misollarni
   o'qib, ularni yechishga yordam ber.
7. Javobni foydalanuvchi ishlatgan tilga moslashtir.
8. Javoblarni iloji boricha batafsil va tartibli yoz.
"""

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "app": "EduAI",
        "status": "online",
        "message": "EduAI backend ishlayapti"
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}

        message = str(data.get("message", "")).strip()
        image_data = data.get("image")

        if not message and not image_data:
            return jsonify({
                "error": "Savol yoki rasm yuboring"
            }), 400

        if image_data:
            if not isinstance(image_data, str):
                return jsonify({"error": "Rasm formati noto'g'ri"}), 400

            if image_data.startswith("data:"):
                parts = image_data.split(",", 1)
                if len(parts) != 2:
                    return jsonify({"error": "Rasm formati noto'g'ri"}), 400

                header, encoded = parts
                mime = header.split(";")[0].replace("data:", "")

                if mime not in (
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                    "image/gif"
                ):
                    return jsonify({
                        "error": "JPEG, PNG, WEBP yoki GIF rasm yuboring"
                    }), 400
            else:
                encoded = image_data
                mime = "image/jpeg"

            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception:
                return jsonify({"error": "Rasmni o'qib bo'lmadi"}), 400

            if len(raw) > 7 * 1024 * 1024:
                return jsonify({"error": "Rasm hajmi juda katta"}), 413

            prompt = message or (
                "Rasmdagi matnni o'qi. Savollar va misollarni "
                "aniqlab, javoblarini bosqichma-bosqich tushuntir."
            )

            completion = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        f"data:{mime};base64,{encoded}"
                                    )
                                }
                            }
                        ]
                    }
                ],
                max_completion_tokens=6000
            )

        else:
            completion = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                max_completion_tokens=6000
            )

        answer = completion.choices[0].message.content or ""

        return jsonify({
            "answer": answer,
            "reply": answer,
            "success": True
        })

    except Exception as e:
        print("EduAI xatosi:", repr(e))
        return jsonify({
            "error": (
                "AI javob bera olmadi. Groq modelini, "
                "API kalitini va limitlarni tekshiring."
            )
        }), 500

@app.errorhandler(413)
def too_large(error):
    return jsonify({"error": "Yuborilgan fayl juda katta"}), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
                
