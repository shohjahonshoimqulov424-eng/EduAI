import os
import base64
import requests
import gradio as gr
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "")

TEXT_MODEL = "llama-3.1-8b-instant"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def ai_answer(question):
    if not GROQ_API_KEY:
        return "Xatolik: Render'da GROQ_API_KEY sozlanmagan."
    if not question or not question.strip():
        return "Savolingizni yozing."

    try:
        client = Groq(api_key=GROQ_API_KEY)
        result = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen EduAI yordamchisisan. "
                        "O'zbek tilida aniq va tushunarli javob ber. "
                        "Foydalanuvchi boshqa tilda so'rasa, "
                        "o'sha tilda javob ber."
                    )
                },
                {"role": "user", "content": question}
            ],
            temperature=0.4,
            max_tokens=3000
        )
        return result.choices[0].message.content
    except Exception as e:
        return f"AI xatosi: {str(e)}"


def translate_text(text, language):
    if not text or not text.strip():
        return "Tarjima uchun matn kiriting."

    prompt = (
        f"Quyidagi matnni {language} tiliga tarjima qil. "
        "Faqat tarjimani emas, zarur bo'lsa qisqa izohni ham ber. "
        "Matnning ma'nosini saqla:\n\n" + text
    )
    return ai_answer(prompt)


def solve_image(image, question):
    if image is None:
        return "Avval rasm yuklang."
    if not GROQ_API_KEY:
        return "Xatolik: GROQ_API_KEY sozlanmagan."

    try:
        import io
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

        client = Groq(api_key=GROQ_API_KEY)
        prompt = (
            "Rasmdagi matn, misol yoki masalani diqqat bilan o'qi. "
            "Matnni tushuntir va masalani bosqichma-bosqich yech. "
            "Agar rasmda test savollari bo'lsa, javoblarni izohla. "
            "Javobni o'zbek tilida yoz. "
            f"Foydalanuvchi izohi: {question or 'Rasmdagi topshiriqni yech.'}"
        )

        result = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encoded}"
                        }
                    }
                ]
            }],
            temperature=0.2,
            max_tokens=3000
        )
        return result.choices[0].message.content
    except Exception as e:
        return f"Rasmni yechishda xatolik: {str(e)}"


def firebase_auth(email, password, action):
    if not FIREBASE_API_KEY:
        return (
            "Firebase kaliti sozlanmagan. Render'da "
            "FIREBASE_API_KEY nomli environment variable qo'shing."
        )

    if not email or not password:
        return "Email va parolni kiriting."

    endpoint_action = (
        "signUp" if action == "signup" else "signInWithPassword"
    )
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:"
        f"{endpoint_action}?key={FIREBASE_API_KEY}"
    )

    try:
        response = requests.post(
            url,
            json={
                "email": email,
                "password": password,
                "returnSecureToken": True
            },
            timeout=20
        )
        data = response.json()

        if response.ok:
            if action == "signup":
                return "Ro'yxatdan o'tdingiz! Endi tizimga kiring."
            return f"Muvaffaqiyatli kirdingiz: {data.get('email', email)}"

        error = data.get("error", {}).get("message", "Noma'lum xato")
        messages = {
            "EMAIL_EXISTS": "Bu email oldin ro'yxatdan o'tgan.",
            "INVALID_EMAIL": "Email manzili noto'g'ri.",
            "WEAK_PASSWORD": "Parol kamida 6 ta belgidan iborat bo'lsin.",
            "INVALID_LOGIN_CREDENTIALS": "Email yoki parol noto'g'ri.",
            "EMAIL_NOT_FOUND": "Bunday email ro'yxatdan o'tmagan."
        }
        return messages.get(error, f"Kirish xatosi: {error}")

    except Exception as e:
        return f"Ulanish xatosi: {str(e)}"


def signup(email, password):
    return firebase_auth(email, password, "signup")


def login(email, password):
    return firebase_auth(email, password, "login")


with gr.Blocks(title="EduAI") as app:
    gr.Markdown(
        """
        # 🎓 EduAI
        ### O'qish va o'qitish uchun sun'iy intellekt
        Savol bering, tarjima qiling yoki rasm orqali masala yeching.
        """
    )

    with gr.Tabs():
        with gr.Tab("🤖 Savol-javob"):
            question = gr.Textbox(
                label="Savolingiz",
                placeholder="Savolingizni shu yerga yozing...",
                lines=4
            )
            ask_button = gr.Button("Javob olish", variant="primary")
            answer = gr.Markdown(label="AI javobi")
            ask_button.click(ai_answer, inputs=question, outputs=answer)

        with gr.Tab("🌐 Tarjimon"):
            source_text = gr.Textbox(
                label="Tarjima qilinadigan matn", lines=5
            )
            target_language = gr.Dropdown(
                choices=["o'zbek tiliga", "rus tiliga", "ingliz tiliga"],
                value="ingliz tiliga",
                label="Qaysi tilga tarjima qilinsin?"
            )
            translate_button = gr.Button("Tarjima qilish")
            translated = gr.Markdown()
            translate_button.click(
                translate_text,
                inputs=[source_text, target_language],
                outputs=translated
            )

        with gr.Tab("📷 Rasm orqali masala yechish"):
            image_input = gr.Image(
                label="Rasm yuklang", type="pil"
            )
            image_question = gr.Textbox(
                label="Qo'shimcha izoh (ixtiyoriy)",
                placeholder="Masalan: 3-masalani yech"
            )
            solve_button = gr.Button("Rasmni yechish", variant="primary")
            solution = gr.Markdown()
            solve_button.click(
                solve_image,
                inputs=[image_input, image_question],
                outputs=solution
            )

        with gr.Tab("📝 Ro'yxatdan o'tish"):
            signup_email = gr.Textbox(label="Email")
            signup_password = gr.Textbox(
                label="Parol", type="password"
            )
            signup_button = gr.Button("Ro'yxatdan o'tish")
            signup_result = gr.Markdown()
            signup_button.click(
                signup,
                inputs=[signup_email, signup_password],
                outputs=signup_result
            )

        with gr.Tab("🔐 Tizimga kirish"):
            login_email = gr.Textbox(label="Email")
            login_password = gr.Textbox(
                label="Parol", type="password"
            )
            login_button = gr.Button("Kirish", variant="primary")
            login_result = gr.Markdown()
            login_button.click(
                login,
                inputs=[login_email, login_password],
                outputs=login_result
            )

        with gr.Tab("💳 Tariflar"):
            gr.Markdown(
                """
                ### EduAI tariflari

                - **1 oy — 100 000 so'm**
                - **3 oy — 300 000 so'm**
                - **1 yil — 800 000 so'm**

                Obunani rasmiylashtirish uchun administrator bilan
                bog'laning. Bu tariflar hozircha ma'lumot uchun;
                avtomatik to'lov tizimi hali ulanmagan.
                """
            )

    gr.Markdown("© EduAI — ta'lim uchun AI yordamchi")


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=int(
        os.environ.get("PORT", 7860)
    ))
