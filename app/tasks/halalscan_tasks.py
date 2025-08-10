import os
import shutil
import asyncio
import requests
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime

# --- Import Pustaka Selenium ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import urllib.parse

# Import Celery and other services
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
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not found.")
    client = genai.Client(api_key=gemini_api_key)
    
    firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
    if not firebase_creds_json:
        raise ValueError("FIREBASE_CREDENTIALS not found.")
    firebase_creds_dict = json.loads(firebase_creds_json)
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_creds_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    documentai_creds_json = os.getenv("DOCUMENTAI_CREDENTIALS")
    if not documentai_creds_json:
        raise ValueError("DOCUMENTAI_CREDENTIALS not found.")
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
    
    print("All services configured for HalalScan Celery task.")

except Exception as e:
    print(f"Error configuring Celery worker: {e}")
    client = None
    db = None
    doc_ai_client = None

# --- Helper functions ---

def ocr_from_file(file_path, mime_type='image/png'):
    """
    Extracts text from an image/PDF using Google Cloud Document AI.
    """
    if not doc_ai_client:
        return ""
    
    try:
        with open(file_path, "rb") as document_file:
            content = document_file.read()
        
        raw_document = documentai.RawDocument(content=content, mime_type=mime_type)
        request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
        response = doc_ai_client.process_document(request=request)
        return response.document.text
    except Exception as e:
        print(f"Error during Document AI OCR: {e}")
        return ""
    
def extract_product_info_from_text(text):
    """
    Extracts product name and producer from OCR text using LLM.
    """
    if not client:
        return "", ""
    
    prompt = f"""
    Anda adalah asisten AI yang ahli dalam mengekstrak NAMA PRODUK dan NAMA PELAKU USAHA dari teks.
    Teks ini berasal dari label kemasan produk. Identifikasi dan berikan hanya NAMA PRODUK dan NAMA PELAKU USAHA.
    Pisahkan keduanya dengan koma. Jika salah satu tidak ditemukan, tulis 'Tidak Ditemukan'.

    Contoh output:
    Sari Roti Roti Tawar Gandum, PT. Indoroti Prima Citarasa

    Teks untuk dianalisis:
    {text}
    """
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        response_text = getattr(response, "text", None)
        if response_text is None:
            print("Error: LLM response text is None.")
            return "", ""
        parts = response_text.strip().split(',', 1)
        product_name = parts[0].strip()
        producer_name = parts[1].strip() if len(parts) > 1 else ""
        return product_name, producer_name
    except Exception as e:
        print(f"Error during product info extraction with LLM: {e}")
        return "", ""

def scrape_bpjph_halal(product_name, pelaku_usaha):
    """
    Melakukan pencarian di situs BPJPH dan menggabungkan hasilnya.
    """
    url_base = "https://bpjph.halal.go.id/search/sertifikat"
    combined_results = {}
    
    try:
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 10)

        def perform_search(search_url):
            driver.get(search_url)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))
                soup = BeautifulSoup(driver.page_source, "html.parser")
                rows = soup.select("table tbody tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 4:
                        item = {
                            "nama_produk": cells[0].get_text(strip=True),
                            "produsen": cells[1].get_text(strip=True),
                            "nomor_sertifikat": cells[2].get_text(strip=True),
                            "tanggal_terbit": cells[3].get_text(strip=True),
                        }
                        if item["nomor_sertifikat"]:
                            combined_results[item["nomor_sertifikat"]] = item
            except TimeoutException:
                print(f"Pencarian di {search_url} tidak menemukan hasil.")

        if product_name and product_name != 'Tidak Ditemukan':
            print(f"Mencari berdasarkan Nama Produk: '{product_name}'...")
            url_produk = f"{url_base}?nama_produk={urllib.parse.quote(product_name)}"
            perform_search(url_produk)
            
        if pelaku_usaha:
            print(f"Mencari berdasarkan Nama Pelaku Usaha: '{pelaku_usaha}'...")
            url_pelaku_usaha = f"{url_base}?nama_pelaku_usaha={urllib.parse.quote(pelaku_usaha)}"
            perform_search(url_pelaku_usaha)

        driver.quit()
    except Exception as e:
        print(f"Terjadi error saat scraping BPJPH: {e}")
    
    return list(combined_results.values())


def summarize_halal_status_with_llm(product_name, bpjph_results):
    """
    Menganalisis hasil scraping dan memberikan ringkasan status halal.
    """
    if not client:
        return {"status": "failed", "summary": "Layanan AI tidak tersedia."}

    results_text = json.dumps(bpjph_results, indent=2, ensure_ascii=False)
    prompt = f"""
    Anda adalah seorang ahli sertifikasi halal. Tugas Anda adalah menganalisis data dari BPJPH untuk produk bernama '{product_name}'.
    
    Data dari BPJPH:
    {results_text}

    Berdasarkan data di atas, berikan analisis dalam format JSON dengan struktur berikut:
    {{
      "status": "kesimpulan_status",
      "validated_product_name": "nama_produk_yang_paling_cocok",
      "certificate_number": "nomor_sertifikat_terkait",
      "producer": "nama_produsen_terkait",
      "summary_message": "Ringkasan singkat dan ramah untuk pengguna."
    }}

    Nilai untuk "kesimpulan_status" harus salah satu dari: "TERDAFTAR_HALAL", "TIDAK_DITEMUKAN", atau "MEMERLUKAN_VERIFIKASI_LANJUTAN".
    Jika ada kecocokan yang kuat, gunakan "TERDAFTAR_HALAL".
    Jika tidak ada data sama sekali atau datanya sangat tidak relevan, gunakan "TIDAK_DITEMUKAN".
    Jika ada beberapa entri yang mirip tetapi tidak ada yang pasti, gunakan "MEMERLUKAN_VERIFIKASI_LANJUTAN".
    Isi field lainnya sesuai dengan entri yang paling relevan.
    """
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        # Membersihkan output LLM agar menjadi JSON yang valid
        response_text = getattr(response, "text", None)
        if response_text is None:
            print("Error: LLM response text is None.")
            return {"status": "failed", "summary_message": "Analisis AI gagal."}
        cleaned_text = response_text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"LLM summarization failed: {e}")
        return {"status": "failed", "summary_message": "Analisis AI gagal."}


# --- Celery Task (MODIFIED) ---
@app.task(bind=True)
def process_halal_scan(self, task_id, file_path=None, input_text=None):
    """
    Handles the HalalScan process from either an uploaded file (OCR) or direct text input.
    """
    result_to_store = {
        "status": "failed",
        "product_name": "N/A",
        "summary_message": "Terjadi kesalahan saat memulai proses.",
        "timestamp": datetime.now().isoformat()
    }

    try:
        product_name = ""
        producer_name = ""

        # MODIFIKASI: Logika untuk memproses input berdasarkan jenisnya
        if file_path:
            print(f"Task {task_id}: Memproses file {file_path}...")
            extracted_text = ocr_from_file(file_path)
            if not extracted_text:
                result_to_store["summary_message"] = "Gagal mengekstrak teks dari gambar."
                raise Exception("OCR failed.")
            
            product_name, producer_name = extract_product_info_from_text(extracted_text)

        elif input_text:
            print(f"Task {task_id}: Memproses teks '{input_text}'...")
            # Jika hanya nama produk yang diberikan, produsen bisa dikosongkan
            product_name = input_text
            producer_name = "" # Atau bisa diekstrak jika formatnya "produk, produsen"

        else:
            result_to_store["summary_message"] = "Tidak ada input yang diberikan (file atau teks)."
            raise ValueError("No input provided.")

        if not product_name or "Tidak Ditemukan" in product_name:
            result_to_store["summary_message"] = "Nama produk tidak dapat diidentifikasi dari input."
            raise Exception("Product name extraction failed.")

        result_to_store["product_name"] = product_name

        # Langkah 2: Scrape BPJPH
        bpjph_results = scrape_bpjph_halal(product_name, producer_name)

        # Langkah 3: Gunakan LLM untuk menyimpulkan status
        summary_result = summarize_halal_status_with_llm(product_name, bpjph_results)
        
        # Gabungkan hasil ringkasan ke dalam hasil akhir
        result_to_store.update(summary_result)
        result_to_store["status"] = "completed" # Menandakan proses celery selesai

    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        # Pesan error sudah diatur di dalam blok try
        
    finally:
        # Simpan hasil akhir (sukses atau gagal) ke Firestore
        if db:
            doc_ref = db.collection('halal_scan_results').document(task_id)
            doc_ref.set(result_to_store)
        else:
            print("Firestore client not available. Cannot save results.")
            
        # Hapus file temporer jika ada
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        print(f"Task {task_id} finished with status: {result_to_store.get('status')}")

