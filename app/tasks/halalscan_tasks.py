import os
import json
import time
from datetime import datetime
import logging

# --- Google Document AI (v1) ---
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.oauth2.service_account import Credentials

# --- Other imports ---
import urllib.parse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# --- Celery and Firebase (kept as in original, adapt to your env) ---
from app.celery_app import app
import firebase_admin
from firebase_admin import credentials, firestore

# ------------------------
# Document AI setup (revised to match RAG Fatwa style)
# - Uses documentai_v1
# - Reads credential JSON from env var DOCUMENTAI_CREDENTIALS
# - Configures client with ClientOptions using LOCATION
# ------------------------
try:
    log = logging.getLogger(__name__)
    documentai_creds_json = os.getenv("DOCUMENTAI_CREDENTIALS")
    if not documentai_creds_json:
        raise ValueError("DOCUMENTAI_CREDENTIALS not found in environment variables")
    documentai_creds_dict = json.loads(documentai_creds_json)
    documentai_credentials = Credentials.from_service_account_info(documentai_creds_dict)

    PROJECT_ID = os.getenv('GCP_PROJECT_ID') or documentai_creds_dict.get('project_id')
    LOCATION = os.getenv('DOCUMENTAI_LOCATION') or 'us'
    PROCESSOR_ID = os.getenv('DOCUMENTAI_PROCESSOR_ID')
    if not PROCESSOR_ID:
        raise ValueError("DOCUMENTAI_PROCESSOR_ID not set in environment variables")

    client_options = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
    doc_ai_client = documentai.DocumentProcessorServiceClient(
        client_options=client_options,
        credentials=documentai_credentials
    )
    processor_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
    print("Document AI client initialized (v1).")
except Exception as e:
    print(f"Document AI configuration error: {e}")
    doc_ai_client = None
    processor_name = None

# --- Firebase init (example) ---
try:
    firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
    firebase_creds = json.loads(firebase_creds_json) if firebase_creds_json else None
    if firebase_creds and not firebase_admin._apps:
        cred = credentials.Certificate(firebase_creds)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized.")
except Exception as e:
    print(f"Firebase init error: {e}")
    db = None

# --- Helper: OCR using Document AI (v1)
def ocr_from_file(file_path, mime_type='application/pdf'):
    """
    Extracts text from file (PDF/image) using Document AI v1.
    Handles imageless fallback when PAGE_LIMIT_EXCEEDED occurs.
    Returns extracted text (string) or empty string on failure.
    """
    if not doc_ai_client or not processor_name:
        print("Document AI client not configured.")
        return ""

    try:
        with open(file_path, 'rb') as f:
            content = f.read()

        raw_document = documentai.RawDocument(content=content, mime_type=mime_type)
        request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)

        try:
            response = doc_ai_client.process_document(request=request)
            return response.document.text or ""
        except Exception as e:
            err_str = str(e)
            # Handle PAGE_LIMIT_EXCEEDED by attempting imageless mode
            if 'PAGE_LIMIT_EXCEEDED' in err_str or 'page limit' in err_str.lower():
                print("PAGE_LIMIT_EXCEEDED detected, attempting imageless processing...")
                try:
                    ocr_config = documentai.OcrConfig(enable_native_pdf_parsing=True)
                    process_options = documentai.ProcessOptions(ocr_config=ocr_config)
                    request_imageless = documentai.ProcessRequest(
                        name=processor_name,
                        raw_document=raw_document,
                        process_options=process_options
                    )
                    response_imageless = doc_ai_client.process_document(request=request_imageless)
                    return response_imageless.document.text or ""
                except Exception as imageless_e:
                    print(f"Imageless processing failed: {imageless_e}")
                    return ""
            else:
                print(f"Document AI processing error: {e}")
                return ""

    except Exception as e:
        print(f"Failed to open/read file for OCR: {e}")
        return ""

# --- LLM / Gemini client placeholder: ensure you use the same LLM client across your project ---
try:
    from google import genai
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if gemini_api_key:
        llm_client = genai.Client()
    else:
        llm_client = None
        print("GEMINI_API_KEY not set")
except Exception as e:
    print(f"Could not configure Gemini client: {e}")
    llm_client = None

def extract_product_info_from_text(text):
    """
    Mengekstrak nama produk dan produsen dari teks menggunakan Gemini.
    Meminta output JSON untuk parsing yang lebih andal.
    """
    if not llm_client:
        print("LLM client not configured. Extraction skipped.")
        return "", ""

    # Gunakan model yang valid dan efisien

    # Prompt yang meminta output JSON
    prompt = f"""
    Analisis teks berikut dan identifikasi "nama_produk" dan "nama_pelaku_usaha".
    Balas HANYA dalam format JSON. Contoh: {{"nama_produk": "Teh Pucuk Harum", "nama_pelaku_usaha": "PT Mayora Indah Tbk"}}.
    Jika salah satu informasi tidak dapat ditemukan, gunakan nilai "Tidak Ditemukan".

    Teks untuk dianalisis:
    ---
    {text}
    ---
    """
    response = None
    try:
        response = llm_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        
        # Logging untuk debugging
        print("--- LLM Extraction Raw Response ---")
        print(response.text)
        print("---------------------------------")

        # Membersihkan dan parsing JSON
        text_to_clean = response.text if response.text is not None else ""
        cleaned_text = text_to_clean.strip().replace('json', '').replace('', '')
        data = json.loads(cleaned_text)
        
        product = data.get("nama_produk", "Tidak Ditemukan")
        producer = data.get("nama_pelaku_usaha", "Tidak Ditemukan")
        
        return product, producer
        
    except json.JSONDecodeError as je:
        resp_text = response.text if response and hasattr(response, "text") else ""
        print(f"LLM extraction JSON parsing error: {je}. Respons tidak valid: {resp_text}")
        return "Gagal Parsing LLM", "" # Mengembalikan nilai yang jelas untuk di-handle
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return "", ""
    if not llm_client:
        return "", ""
    prompt = f"Identifikasi NAMA PRODUK dan NAMA PELAKU USAHA dari teks berikut.\n{text}"
    try:
        response = llm_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text_out = response.text if hasattr(response, 'text') and response.text is not None else str(response)
        parts = text_out.strip().split(',', 1)
        product = parts[0].strip() if parts else ''
        producer = parts[1].strip() if len(parts) > 1 else ''
        return product, producer
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return "", ""

# --- BPJPH scraping: keep original but you may replace Selenium with requests if needed ---
def scrape_bpjph_halal(product_name, pelaku_usaha):
    url_base = "https://bpjph.halal.go.id/search/sertifikat"
    combined_results = {}

    try:
        options = ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 10)

        def perform_search(search_url):
            driver.get(search_url)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table tbody tr')))
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                rows = soup.select('table tbody tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 4:
                        item = {
                            'nama_produk': cells[0].get_text(strip=True),
                            'produsen': cells[1].get_text(strip=True),
                            'nomor_sertifikat': cells[2].get_text(strip=True),
                            'tanggal_terbit': cells[3].get_text(strip=True),
                        }
                        if item['nomor_sertifikat']:
                            combined_results[item['nomor_sertifikat']] = item
            except TimeoutException:
                print(f'No results for {search_url}')

        if product_name and product_name != 'Tidak Ditemukan':
            url_produk = f"{url_base}?nama_produk={urllib.parse.quote(product_name)}"
            perform_search(url_produk)
        if pelaku_usaha:
            url_pelaku = f"{url_base}?nama_pelaku_usaha={urllib.parse.quote(pelaku_usaha)}"
            perform_search(url_pelaku)

        driver.quit()
    except Exception as e:
        print(f"BPJPH scraping error: {e}")

    return list(combined_results.values())

# --- LLM summarization placeholder ---
def summarize_halal_status_with_llm(product_name, bpjph_results):
    if not llm_client:
        return {"status": "failed", "summary_message": "LLM not configured"}
    try:
        prompt = f"Analisis status halal untuk produk: {product_name}\nData: {json.dumps(bpjph_results, ensure_ascii=False)}"
        response = llm_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text_out = response.text if hasattr(response, 'text') and response.text is not None else str(response)
        # Expecting JSON-like output; attempt to parse
        cleaned = text_out.strip() if text_out is not None else ""
        try:
            return json.loads(cleaned)
        except Exception:
            return {"status": "MEMERLUKAN_VERIFIKASI_LANJUTAN", "validated_product_name": product_name, "certificate_number": "", "producer": "", "summary_message": cleaned}
    except Exception as e:
        print(f"LLM summarization error: {e}")
        return {"status": "failed", "summary_message": "LLM error"}

# --- Celery Task (revised Document AI usage) ---
@app.task(bind=True)
def process_halal_scan(self, task_id, file_path=None, input_text=None):
    result_to_store = {
        'status': 'failed',
        'product_name': 'N/A',
        'summary_message': 'Error while processing',
        'timestamp': datetime.utcnow().isoformat()
    }

    try:
        product_name = ''
        producer_name = ''

        if file_path:
            print(f"Task {task_id}: OCR for {file_path}")
            # try pdf first, if not pdf try image
            mime = 'application/pdf' if file_path.lower().endswith('.pdf') else 'image/png'
            extracted_text = ocr_from_file(file_path, mime_type=mime)
            if not extracted_text:
                result_to_store['summary_message'] = 'Failed to extract text via Document AI.'
            product_name, producer_name = extract_product_info_from_text(extracted_text)

        elif input_text:
            product_name = input_text
            producer_name = ''
        else:
            result_to_store['summary_message'] = 'No input provided.'
            raise ValueError('No input')

        if not product_name or 'Tidak Ditemukan' in product_name:
            result_to_store['summary_message'] = 'Product name could not be identified.'
            raise Exception(f'Product name extraction failed {product_name}')

        result_to_store['product_name'] = product_name

        bpjph_results = scrape_bpjph_halal(product_name, producer_name)
        summary_result = summarize_halal_status_with_llm(product_name, bpjph_results)

        result_to_store.update(summary_result)
        result_to_store['status'] = 'completed'

    except Exception as e:
        print(f"Task {task_id} failed: {e}")
    finally:
        if db:
            try:
                doc_ref = db.collection('halal_scan_results').document(task_id)
                doc_ref.set(result_to_store)
            except Exception as e:
                print(f"Failed to save to Firestore: {e}")
        else:
            print("No Firestore client available; skipping save.")

        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Failed to remove temp file: {e}")

        print(f"Task {task_id} finished with status: {result_to_store.get('status')}")

# --- End of revised HalalScan ---
