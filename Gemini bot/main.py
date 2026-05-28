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

@app.api_route("/", methods=["GET", "POST"])
async def process_yemot(request: Request):
    # נשלוף את כל הפרמטרים
    params = dict(request.query_params)
    
    # ננסה לקבל את ה-val (לפי הלוגים, זה מה שימות המשיח שולחת)
    file_path = params.get("val")
    
    # אם לא מצאנו val, אולי ימות המשיח שולחת תחת שם אחר, 
    # אז ננסה גם את RecordFile ליתר ביטחון (זה לא יזיק)
    if not file_path:
        file_path = params.get("RecordFile")
    if not file_path:
        # מחזירים שגיאה בפורמט שימות יודעת להקריא (טקסט לדיבור)
         return PlainTextResponse("id_list_message=t-שגיאה. לא התקבל נתיב להקלטה.")

    # 1. הורדת הקובץ מימות המשיח
    download_url = f"https://www.call2all.co.il/ym/api/DownloadFile?token={yemot_token}&path={file_path}"
    
    # תוספת קטנה כדי לראות ב-Logs מה הכתובת שהשרת מנסה להוריד ממנה
    print(f"DEBUG: Trying to download from: {download_url}")
    
    try:
        response = requests.get(download_url)
        # נוסיף לוג גם לסטטוס שקיבלנו מהשרת של ימות
        print(f"DEBUG: Yemot response status: {response.status_code}")
        
        if response.status_code != 200:
            return PlainTextResponse("id_list_message=t-שגיאה בהורדת הקובץ מהשרת")
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
