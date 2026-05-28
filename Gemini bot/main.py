from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import google.generativeai as genai
import requests
import os
import re

app = FastAPI()

# --- משתנה גלובלי לשמירת זיכרון השיחות לפי מספר טלפון ---
user_histories = {}

# --- הגדרות ---
# משיכת המפתח החדש והמאובטח מה-Variables של Railway
GOOGLE_API_KEY = os.environ.get("MY_GOOGLE_KEY")
YEMOT_TOKEN = "0773363481:8553876"

genai.configure(api_key=GOOGLE_API_KEY)
# שימוש במודל העדכני והנתמך
model = genai.GenerativeModel(
    model_name="gemini-3.1-flash-lite",
    system_instruction="אתה עוזר קולי של מערכת טלפונית. עליך לתת תשובה ישירה, קצרה מאוד (עד 2 משפטים). בלי הקדמות, בלי רשימות, ורק במילים פשוטות שמתאימות לדיבור."
)

@app.api_route("/", methods=["GET", "POST"])
async def process_yemot(request: Request):
    params = dict(request.query_params)
    
    # 1. שליפת נתיב הקובץ מימות המשיח
    file_path = params.get("val") or params.get("RecordFile")
    
    # תיקון הקידומת לנתיב הקובץ (ה-ivr2: שגילנו בלוגים)
    if file_path and not file_path.startswith("ivr2:"):
        file_path = f"ivr2:{file_path}"
        
    if not file_path:
        return PlainTextResponse("id_list_message=t-שגיאה. לא התקבל נתיב להקלטה.")

    # 2. שליפת מספר הטלפון של המתקשר לצורך ניהול הזיכרון
    phone = params.get("ApiPhone", "unknown_user")

    # 3. בניית כתובת ההורדה מימות המשיח
    download_url = f"https://www.call2all.co.il/ym/api/DownloadFile?token={YEMOT_TOKEN}&path={file_path}"
    print(f"DEBUG: Trying to download from: {download_url}")
    
    # הגדרת נתיבים זמניים ומספר משתנים מראש
    temp_file_path = f"temp_{os.urandom(4).hex()}.wav"
    uploaded_audio = None

    try:
        # ביצוע ההורדה של קובץ השמע מהטלפון
        response = requests.get(download_url)
        if response.status_code != 200:
            return PlainTextResponse("id_list_message=t-השרת לא הצליח להוריד את ההקלטה")

        # שמירת הקובץ באופן זמני בשרת של Railway
        with open(temp_file_path, "wb") as f:
            f.write(response.content)

        # 4. ניהול הזיכרון הקצר (עד 3 הודעות אחרונות)
        if phone not in user_histories:
            user_histories[phone] = []
            
        history_text = "\n".join(user_histories[phone])
        
        # יצירת ההנחיה לג'ימיני שכוללת את מה שנאמר בשיחה עד כה
        prompt = f"היסטוריית השיחה הקודמת עם המשתמש הנוכחי:\n{history_text}\n\nהקשב להקלטה הנוכחית המצורפת וענה לו ישירות."

        # 5. העלאת הקובץ לגוגל וקבלת תגובה
        uploaded_audio = genai.upload_file(temp_file_path)
        gen_response = model.generate_content([uploaded_audio, prompt])
        raw_text = gen_response.text

        # 6. עדכון הזיכרון של המשתמש בתגובה החדשה של הבוט
        user_histories[phone].append(f"ענית לו: {raw_text}")
        if len(user_histories[phone]) > 3:
            user_histories[phone].pop(0) # מחיקת ההודעה הישנה ביותר כדי לחסוך מקום ומכסה

        # 7. ניקוי אגרסיבי של הטקסט לפני השליחה חזרה לטלפון
        cleaned_text = raw_text.replace('\n', ' ').replace('\r', ' ')
        cleaned_text = re.sub(r'[*#_`~"\'\-:\\]', '', cleaned_text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        # החזרת התשובה למערכת הטלפונית
        yemot_response = f"id_list_message=t-{cleaned_text}"
        return PlainTextResponse(yemot_response)

    except Exception as e:
        print(f"Error occurred: {e}")
        return PlainTextResponse("id_list_message=t-הייתה תקלה בתקשורת או בעיבוד הנתונים.")
    
    finally:
        # 8. ניקוי ומחיקת קבצים - שומר על שטח אחסון חינמי ונקי!
        # מחיקת הקובץ הזמני משרת Railway
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        # מחיקת הקובץ מהשרתים של גוגל (Google AI Studio) כדי שלא יתמלא האחסון
        if uploaded_audio:
            try:
                genai.delete_file(uploaded_audio.name)
                print("DEBUG: Successfully deleted audio from Google servers.")
          except Exception as e:
        # זה ידפיס בלוגים את השגיאה המדויקת שקורית
        print(f"CRITICAL ERROR: {str(e)}")
        return PlainTextResponse(f"id_list_message=t-שגיאה: {str(e)}")
