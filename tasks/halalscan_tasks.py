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
from celery_app import app
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.oauth2.service_account import Credentials
from google import genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- Konfigurasi Kredensial (untuk lingkungan background worker) ---
try:
    # Use environment variables to get credentials
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
    
    print("All services configured for Celery task.")

except Exception as e:
    print(f"Error configuring Celery worker: {e}")
    db = None
    doc_ai_client = None

# --- Helper functions (Implementasi Nyata) ---

def ocr_document_ai(file_path, client, processor_name):
    """
    Extracts text from an image/PDF using Google Cloud Document AI.
    """
    if not client:
        return ""
    
    try:
        with open(file_path, "rb") as image_file:
            content = image_file.read()
        
        raw_document = documentai.RawDocument(content=content, mime_type='image/png')
        request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
        response = client.process_document(request=request)
        return response.document.text
    except Exception as e:
        print(f"Error during Document AI OCR: {e}")
        return ""
    
def extract_product_name(text):
    """
    Extracts product name from OCR text using LLM for more robust results.
    """
    if not client:
        return ""
    
    prompt = f"""
    Anda adalah asisten AI yang ahli dalam mengekstrak nama produk dari teks label.
    Tugas Anda adalah membaca teks di bawah dan mengidentifikasi NAMA PRODUK dan PELAKU USAHA.
    Teks ini diambil dari label kemasan produk. Berikan hanya NAMA PRODUK yang paling mungkin dan PELAKU USAHA yang tertera, dipisahkan oleh koma.
    Jika tidak ditemukan, berikan 'Tidak Ditemukan'.

    Contoh output:
    Sari Roti Roti Tawar Gandum, PT. Indoroti Prima Citarasa

    Teks untuk dianalisis:
    {text}
    """
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        print(f"Error during product name extraction with LLM: {e}")
        return ""

def scrape_bpjph_halal(product_name, pelaku_usaha):
    """
    Melakukan pencarian di situs BPJPH (berdasarkan nama produk dan pelaku usaha)
    dan menggabungkan hasilnya ke dalam satu daftar.
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

        # --- Fungsi pembantu untuk melakukan satu kali pencarian ---
        def perform_search_and_scrape(search_url):
            driver.get(search_url)
            
            try:
                # Tunggu sampai baris tabel muncul
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))
                
                # Jika tabel ditemukan, scrape datanya
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
                        # Menggunakan nomor sertifikat sebagai kunci untuk menghindari duplikasi
                        if item["nomor_sertifikat"]:
                            combined_results[item["nomor_sertifikat"]] = item
            except TimeoutException:
                print(f"Pencarian tidak menemukan hasil dalam 10 detik.")
                # Lanjutkan ke pencarian berikutnya jika timeout

        # --- Jalankan pencarian pertama: Nama Produk ---
        if product_name:
            print(f"Mencari berdasarkan Nama Produk: '{product_name}'...")
            url_produk = f"{url_base}?nama_produk={urllib.parse.quote(product_name)}"
            perform_search_and_scrape(url_produk)
            
        # --- Jalankan pencarian kedua: Nama Pelaku Usaha ---
        if pelaku_usaha:
            print(f"\nMencari berdasarkan Nama Pelaku Usaha: '{pelaku_usaha}'...")
            url_pelaku_usaha = f"{url_base}?nama_pelaku_usaha={urllib.parse.quote(pelaku_usaha)}"
            perform_search_and_scrape(url_pelaku_usaha)

        driver.quit()
        
    except Exception as e:
        print(f"Terjadi error saat menjalankan scraping: {e}")
        return []

    return list(combined_results.values())


def summarize_halal_status_with_llm(product_name, bpjph_results):
    """
    Uses Gemini to analyze scraping results and determine halal status.
    """
    if not client:
        return {"status": "failed", "halal_status": "Layanan AI tidak tersedia."}

    results_text = json.dumps(bpjph_results, indent=2)
    prompt = f"""
    Anda adalah asisten AI yang ahli dalam menyimpulkan status halal produk.
    Berdasarkan hasil pencarian sertifikasi BPJPH berikut, tentukan apakah produk dengan nama '{product_name}' bersertifikat halal.
    Tinjau setiap entri, dan berikan kesimpulan akhir yang jelas.

    Hasil Pencarian BPJPH:
    {results_text}

    Kesimpulan:
    1. Status Halal: [HALAL/TIDAK HALAL/BELUM TERDAFTAR]
    2. Nama Produk Tervalidasi: [Nama Produk di BPJPH, jika ada]
    3. Nomor Sertifikat: [Nomor Sertifikat, jika ada]
    4. Pesan: [Berikan ringkasan singkat yang ramah pengguna.]
    """
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return {"status": "completed", "result": response.text}
    except Exception as e:
        print(f"LLM summarization failed: {e}")
        return {"status": "failed", "halal_status": "Kesimpulan AI gagal."}


# --- Celery Task ---
@app.task(bind=True)
def process_halal_scan(self, file_path, task_id):
    """
    Handles the entire HalalScan process: OCR, scraping, LLM analysis, and storage.
    """
    halal_status = {
        "status": "failed",
        "product_name": "Tidak Ditemukan",
        "producer_name": "Tidak Ditemukan",
        "halal_status": "Tidak Ditemukan",
        "message": "Terjadi kesalahan saat memproses dokumen."
    }

    try:
        # Step 1: OCR the uploaded image using Document AI
        extracted_text = ocr_document_ai(file_path, doc_ai_client, processor_name)
        if not extracted_text:
            halal_status["message"] = "Gagal mengekstrak teks dari gambar."
            raise Exception("OCR failed.")

        # Step 2: Identify product name from the extracted text using LLM
        product_name_llm_response = extract_product_name(extracted_text)
        # Assuming LLM response is 'Product Name, Producer Name'
        if product_name_llm_response is not None and "," in product_name_llm_response:
            product_name, producer_name = product_name_llm_response.split(',', 1)
            product_name = product_name.strip()
            producer_name = producer_name.strip()
        else:
            product_name = product_name_llm_response.strip() if product_name_llm_response else ""
            producer_name = ""

        if not product_name or "Tidak Ditemukan" in product_name:
            halal_status["message"] = "Nama produk tidak dapat diidentifikasi."
            raise Exception("Product name extraction failed.")

        # Step 3: Scrape BPJPH for the product
        bpjph_results = scrape_bpjph_halal(product_name, producer_name)

        # Step 4: Use LLM to summarize and determine the halal status
        if bpjph_results:
            halal_status_result = summarize_halal_status_with_llm(product_name, bpjph_results)
            
            # This is a basic example; parsing LLM output to JSON is a future step
            halal_status["halal_status"] = "Halal" if "HALAL" in halal_status_result['result'] else "Tidak Halal"
            halal_status["message"] = "Verifikasi berhasil. Silakan periksa detailnya."
        else:
            halal_status["halal_status"] = "Belum Terdaftar"
            halal_status["message"] = "Tidak ada produk yang relevan ditemukan di BPJPH."
        
        halal_status["product_name"] = product_name
        halal_status["producer_name"] = producer_name
        halal_status["timestamp"] = datetime.now().isoformat()

        # Step 5: Store the final result in Firestore
        if db:
            doc_ref = db.collection('halal_status_cache').document(task_id)
            doc_ref.set(halal_status)
        else:
            print("Firestore client not available. Cannot save results.")
            
    except Exception as e:
        print(f"HalalScan task failed with error: {e}")
        # Store a failure status in Firestore
        if db:
            doc_ref = db.collection('halal_status_cache').document(task_id)
            doc_ref.set(halal_status)
    finally:
        # Clean up the temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

