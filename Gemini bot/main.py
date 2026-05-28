from fastapi import FastAPI, File, UploadFile
import google.generativeai as genai
import os
import re

app = FastAPI()

# הכנס את מפתח ה-API שלך כאן
GOOGLE_API_KEY = "AIzaSyDl6bBcpl-CQdupFbkT4AtuZMFCAlyZ75k"
genai.configure(api_key=GOOGLE_API_KEY)

# הגדרת הוראות המערכת (System Instructions) לתשובות קוליות קצרות
system_instruction = """
אתה עוזר קולי המנהל דו-שיח מדובר עם המשתמש.
עליך לספק תשובות קצרות מאוד, ממוקדות וטבעיות לשיחה קולית (עד 2-3 משפטים בלבד).
אל תשתמש ברשימות, כותרות, או הדגשות. דבר בצורה ישירה ופשוטה.
"""

# שימוש במודל הפלאש (המהיר ביותר) עם הוראות המערכת
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=system_instruction
)

@app.post("/process-audio")
async def process_audio(audio_file: UploadFile = File(...)):
    # שמירת הקובץ באופן זמני
    temp_file_path = f"temp_{audio_file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await audio_file.read())

    try:
        # העלאת הקובץ ל-Gemini
        uploaded_audio = genai.upload_file(temp_file_path)

        # בקשת יצירת התוכן. ג'מיני יתמלל ויענה בפעולה אחת.
        response = model.generate_content(
            [uploaded_audio, "אנא ענה על הנאמר בהקלטה זו בהתאם להוראות שלך."]
        )

        raw_text = response.text

        # --- ניקוי הטקסט ---
        # 1. הסרת ירידות שורה והחלפתן ברווח
        cleaned_text = raw_text.replace('\n', ' ').replace('\r', ' ')
        # 2. הסרת סימני מחיצה של מארקאון כגון כוכביות, סולמיות, קווים תחתונים
        cleaned_text = re.sub(r'[*#_`~-]', '', cleaned_text)
        # 3. צמצום רווחים כפולים לרווח אחד
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        # החזרת הטקסט הנקי בלבד
        return {"text_response": cleaned_text}

    except Exception as e:
        return {"error": str(e)}

    finally:
        # מחיקת הקובץ הזמני כדי לא לחסום את הזיכרון
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# פקודת ההרצה של השרת המקומי (לצורך בדיקות):
# uvicorn main:app --host 0.0.0.0 --port 8000