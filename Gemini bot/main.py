from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import google.generativeai as genai
import requests
import os
import re

app = FastAPI()

# --- הגדרות ---
# שים לב: כדאי להחליף את המפתחות האלו בהקדם כי הם נחשפו
GOOGLE_API_KEY = os.environ.get("MY_GOOGLE_KEY")
YEMOT_TOKEN = "0773363481:8553876"

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="אתה עוזר קולי של מערכת טלפונית. עליך לתת תשובה ישירה, קצרה מאוד (עד 2 משפטים). בלי הקדמות, בלי רשימות, ורק במילים פשוטות שמתאימות לדיבור."
)

@app.api_route("/", methods=["GET", "POST"])
async def process_yemot(request: Request):
    params = dict(request.query_params)
   
    # שליפת הנתיב
    file_path = params.get("val") or params.get("RecordFile")
    if file_path and not file_path.startswith("ivr2:"):
        file_path = f"ivr2:{file_path}"
    if not file_path:
        return PlainTextResponse("id_list_message=t-שגיאה. לא התקבל נתיב להקלטה.")

    # 1. הורדת הקובץ מימות המשיח (המשתנה עכשיו באותיות גדולות כפי שהוגדר)
    download_url = f"https://www.call2all.co.il/ym/api/DownloadFile?token={YEMOT_TOKEN}&path={file_path}"
    print(f"DEBUG: Trying to download from: {download_url}")
   
    # הגדרת נתיב הקובץ הזמני
    temp_file_path = f"temp_{os.urandom(4).hex()}.wav"

    try:
        # ביצוע ההורדה
        response = requests.get(download_url)
        if response.status_code != 200:
            return PlainTextResponse("id_list_message=t-השרת לא הצליח להוריד את ההקלטה")

        # שמירת הקובץ באופן זמני בשרת שלך (הוכנס לתוך ה-try)
        with open(temp_file_path, "wb") as f:
            f.write(response.content)

        # 3. העלאת הקובץ לג'מיני ובקשת תמלול + תגובה
        uploaded_audio = genai.upload_file(temp_file_path)
        gen_response = model.generate_content([uploaded_audio, "ענה על הנאמר בהקלטה."])
        raw_text = gen_response.text

        # 4. ניקוי אגרסיבי של הטקסט
        cleaned_text = raw_text.replace('\n', ' ').replace('\r', ' ')
        cleaned_text = re.sub(r'[*#_`~"\'\-:\\]', '', cleaned_text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        # 5. החזרת התשובה לימות המשיח
        yemot_response = f"id_list_message=t-{cleaned_text}"
        return PlainTextResponse(yemot_response)

    except Exception as e:
        print(f"Error occurred: {e}")
        return PlainTextResponse("id_list_message=t-הייתה תקלה בתקשורת מול גוגל או השרת.")
   
    finally:
        # מחיקת הקובץ הזמני מתבצעת תמיד, גם אם הייתה שגיאה
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
