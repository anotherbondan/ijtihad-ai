from celery import Celery
import os
from dotenv import load_dotenv

# Memuat variabel lingkungan dari file .env
load_dotenv()

# Mengambil URL Redis dari variabel lingkungan, dengan fallback ke localhost
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Menginisialisasi Celery app
# Parameter pertama ('backend') adalah nama modul utama aplikasi.
app = Celery('ijtihad', broker=REDIS_URL, backend=REDIS_URL, include=['app.tasks.halalscan_tasks', 'app.tasks.ghararmaysir_tasks'])

# Mengatur Celery untuk menemukan tugas di dalam paket 'backend.tasks'
# Ini memungkinkan Celery untuk secara otomatis menemukan fungsi
# yang dihiasi dengan @app.task di dalam folder tasks/.
app.autodiscover_tasks(['app.tasks'])

# Mengatur konfigurasi tambahan
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Jakarta',
    enable_utc=True,
    broker_connection_retry_on_startup=True
)
