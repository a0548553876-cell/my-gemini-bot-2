from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import google.generativeai as genai
import requests
import os
import re

app = FastAPI()

GOOGLE_API_KEY = os.environ.get("MY_GOOGLE_KEY")
YEMOT_TOKEN = "0773363481:8553876"

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-1.5-flash") # נסה שוב את זה, או שתחליף לשם המדויק מהרשימה שלך

@app.api_route("/", methods=["GET", "POST"])
async def process_yemot(request: Request):
    params = dict(request.query_params)
    file_path = params.get("val") or params.get("RecordFile")
    
    if file_path and not file_path.startswith("ivr2:"):
        file_path = f"ivr2:{file_path}"
    if not file_path:
        return PlainTextResponse("id_list_message=t-שגיאה בנתיב.")

    download_url = f"https://www.call2all.co.il/ym/api/DownloadFile?token={YEMOT_TOKEN}&path={file_path}"
    temp_file_path = f"temp_{os.urandom(4).hex()}.wav"

    try:
        response = requests.get(download_url)
        with open(temp_file_path, "wb") as f:
            f.write(response.content)

        uploaded_audio = genai.upload_file(temp_file_path)
        gen_response = model.generate_content([uploaded_audio, "ענה על הנאמר בהקלטה בקצרה."])
        
        cleaned_text = re.sub(r'[*#_`~"\'\-:\\]', '', gen_response.text)
        
        genai.delete_file(uploaded_audio.name) # מחיקה מגוגל
        return PlainTextResponse(f"id_list_message=t-{cleaned_text}")

    except Exception as e:
        print(f"ERROR: {e}")
        return PlainTextResponse("id_list_message=t-תקלה בשרת.")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
