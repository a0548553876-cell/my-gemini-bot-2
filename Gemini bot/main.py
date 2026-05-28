from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import google.generativeai as genai
import requests
import os
import re

app = FastAPI()

# --- הגדרות ---
GOOGLE_API_KEY = "AIzaSyDl6bBcpl-CQdupFbkT4AtuZMFCAlyZ75k"
YEMOT_TOKEN = "0773363481:8553876" # הטוקן של ימות המשיח (מספר המערכת:סיסמת ניהול)

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="אתה עוזר קולי של מערכת טלפונית. עליך לתת תשובה ישירה, קצרה מאוד (עד 2 משפטים). בלי הקדמות, בלי רשימות, ורק במילים פשוטות שמתאימות לדיבור."
)

@app.api_route("/process-yemot", methods=["GET", "POST"])
async def process_yemot(request: Request):
    # 1. קליטת הנתיב שימות המשיח שולחת. 
    # נניח שבהגדרות API בימות המשיח קראת למשתנה ההקלטה RecordFile
    params = request.query_params
    file_path = params.get("RecordFile")

    if not file_path:
        # מחזירים שגיאה בפורמט שימות יודעת להקריא (טקסט לדיבור)
         return PlainTextResponse("id_list_message=t-שגיאה. לא התקבל נתיב להקלטה.")

    # 2. הורדת קובץ השמע מהשרתים של ימות המשיח (API Call2All)
    download_url = f"https://www.call2all.co.il/ym/api/DownloadFile?token={YEMOT_TOKEN}&path={file_path}"
    response = requests.get(download_url)

    if response.status_code != 200:
         return PlainTextResponse("id_list_message=t-שגיאה. השרת לא הצליח להוריד את ההקלטה.")

    # שמירת הקובץ באופן זמני בשרת שלך
    temp_file_path = f"temp_{os.urandom(4).hex()}.wav"
    with open(temp_file_path, "wb") as f:
        f.write(response.content)

    try:
        # 3. העלאת הקובץ לג'מיני ובקשת תמלול + תגובה
        uploaded_audio = genai.upload_file(temp_file_path)
        gen_response = model.generate_content([uploaded_audio, "ענה על הנאמר בהקלטה."])
        raw_text = gen_response.text

        # 4. ניקוי אגרסיבי של הטקסט
        # הורדת שורות חדשות
        cleaned_text = raw_text.replace('\n', ' ').replace('\r', ' ')
        # מחיקת כל סימן קריאה, פסיק כפול, מרכאות, כוכביות, מקפים שעלולים לשבור את ימות המשיח
        cleaned_text = re.sub(r'[*#_`~"\'\-:\\]', '', cleaned_text)
        # צמצום רווחים מיותרים
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        # 5. בניית התשובה לימות המשיח
        # שימוש ב-PlainTextResponse כדי למנוע יצירת JSON.
        # הפורמט id_list_message=t-Text אומר לימות המשיח לפתוח מנוע TTS ולהקריא.
        yemot_response = f"id_list_message=t-{cleaned_text}"
        
        return PlainTextResponse(yemot_response)

    except Exception as e:
        return PlainTextResponse("id_list_message=t-הייתה תקלה בתקשורת מול גוגל.")
    
    finally:
        # מחיקת הקובץ הזמני
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
