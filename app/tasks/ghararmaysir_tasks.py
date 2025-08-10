import os
import shutil
import json
from datetime import datetime

from app.celery_app import app
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.oauth2.service_account import Credentials
from google import genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- Konfigurasi Kredensial (diasumsikan sudah di-set di environment) ---
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client()
    
    firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
    if firebase_creds_json is None:
        raise ValueError("FIREBASE_CREDENTIALS environment variable is not set.")
    firebase_creds_dict = json.loads(firebase_creds_json)
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_creds_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    documentai_creds_json = os.getenv("DOCUMENTAI_CREDENTIALS")
    if documentai_creds_json is None:
        raise ValueError("DOCUMENTAI_CREDENTIALS environment variable is not set.")
    documentai_creds_dict = json.loads(documentai_creds_json)
    documentai_credentials = Credentials.from_service_account_info(documentai_creds_dict)
    
    PROJECT_ID = os.getenv('GCP_PROJECT_ID') 
    LOCATION = os.getenv('DOCUMENTAI_LOCATION')
    PROCESSOR_ID = os.getenv('DOCUMENTAI_PROCESSOR_ID')
    client_options = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
    doc_ai_client = documentai.DocumentProcessorServiceClient(
        client_options=client_options,
        credentials=documentai_credentials
    )
    processor_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
    
    print("All services configured for Syariah Analysis Celery task.")

except Exception as e:
    print(f"Error configuring Celery worker: {e}")
    client = None
    db = None
    doc_ai_client = None

# --- Helper functions ---

# MODIFIKASI: Fungsi OCR dibuat lebih generik dengan parameter mime_type
def ocr_from_file(file_path, mime_type):
    """
    Extracts text from a file (PDF, PNG, JPG) using Google Cloud Document AI.
    """
    if not doc_ai_client:
        print("Document AI client not configured.")
        return ""
    
    if not mime_type:
        raise ValueError("MIME type is required for OCR processing.")

    try:
        with open(file_path, "rb") as document_file:
            content = document_file.read()
        
        raw_document = documentai.RawDocument(content=content, mime_type=mime_type)
        request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
        response = doc_ai_client.process_document(request=request)
        return response.document.text
    except Exception as e:
        print(f"Error during Document AI OCR for mime_type {mime_type}: {e}")
        return ""

def analyze_with_llm(contract_text):
    """
    Menganalisis teks kontrak untuk indikasi gharar/maysir menggunakan LLM.
    """
    if not client:
        return {"indicators": [], "summary": "Layanan AI tidak tersedia."}

    prompt = f"""
    Anda adalah seorang ahli hukum kontrak syariah. Analisis teks kontrak berikut untuk mengidentifikasi klausul yang mengandung unsur GHARAR (ketidakpastian) atau MAYSIR (spekulasi/judi).

    Berikan hasil analisis dalam format JSON dengan struktur:
    {{
      "indicators": [
        {{ "type": "gharar", "phrase": "kutipan klausul yang bermasalah", "reason": "alasan syariah singkat kenapa ini gharar" }},
        {{ "type": "maysir", "phrase": "kutipan klausul yang bermasalah", "reason": "alasan syariah singkat kenapa ini maysir" }}
      ],
      "summary": "Ringkasan umum mengenai tingkat kepatuhan syariah dari kontrak ini."
    }}

    Jika tidak ada indikasi, kembalikan array "indicators" yang kosong.

    Teks Kontrak:
    {contract_text}
    """
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        if response.text is not None:
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_text)
        else:
            print("LLM response text is None.")
            return {"indicators": [], "summary": "Analisis AI gagal menghasilkan format yang benar."}
    except Exception as e:
        print(f"Error during LLM contract analysis: {e}")
        return {"indicators": [], "summary": "Analisis AI gagal menghasilkan format yang benar."}

def calculate_syariah_clarity_score(indicators):
    """
    Menghitung skor berdasarkan jumlah dan jenis indikator yang ditemukan.
    """
    score = 100
    for indicator in indicators:
        if indicator['type'] == 'gharar':
            score -= 10 # Penalti lebih besar untuk gharar
        elif indicator['type'] == 'maysir':
            score -= 20 # Penalti paling besar untuk maysir
    return max(0, score)


# --- Celery Task (MODIFIED) ---
@app.task(bind=True)
def process_contract_analysis(self, task_id, file_path=None, mime_type=None, text_input=None):
    """
    Menangani analisis kontrak dari file (PDF/Gambar) atau teks langsung.
    """
    analysis_result = {
        "status": "failed",
        "score": 0,
        "indicators": [],
        "summary": "Terjadi kesalahan saat memulai analisis.",
        "timestamp": datetime.now().isoformat()
    }

    try:
        contract_text = ""

        # MODIFIKASI: Logika untuk memproses input berdasarkan jenisnya
        if text_input:
            print(f"Task {task_id}: Menganalisis teks langsung...")
            contract_text = text_input

        elif file_path and mime_type:
            print(f"Task {task_id}: Menganalisis file {file_path} dengan tipe {mime_type}...")
            contract_text = ocr_from_file(file_path, mime_type)
            if not contract_text:
                analysis_result["summary"] = "Gagal mengekstrak teks dari dokumen yang diunggah."
                raise Exception("OCR process failed.")
        
        else:
            analysis_result["summary"] = "Input tidak valid. Diperlukan teks atau file dengan tipe MIME."
            raise ValueError("Invalid input provided.")

        # Langkah 2: Analisis teks dengan LLM
        llm_analysis = analyze_with_llm(contract_text)
        indicators = llm_analysis.get('indicators', [])
        summary = llm_analysis.get('summary', "Ringkasan tidak tersedia.")
        
        # Langkah 3: Hitung skor
        score = calculate_syariah_clarity_score(indicators)

        analysis_result.update({
            "status": "completed",
            "score": score,
            "indicators": indicators,
            "summary": summary
        })
        
    except Exception as e:
        print(f"Task {task_id} for contract analysis failed: {e}")
        # Pesan error sudah diatur di dalam blok try
        
    finally:
        # Simpan hasil ke Firestore
        if db:
            doc_ref = db.collection('syariah_analysis_results').document(task_id)
            doc_ref.set(analysis_result)
        else:
            print("Firestore client not available. Cannot save results.")

        # Hapus file temporer jika ada
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        print(f"Task {task_id} finished with status: {analysis_result.get('status')}")
