import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import exceptions as firebase_exceptions
import json
import os
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Import UserSecretsClient only if running on Kaggle
try:
    from kaggle_secrets import UserSecretsClient # type: ignore
    ON_KAGGLE = True
except ImportError:
    ON_KAGGLE = False
    from dotenv import load_dotenv
    load_dotenv() # Load environment variables from .env if not on Kaggle

# --- Firebase Initialization ---
try:
    if ON_KAGGLE:
        user_secrets = UserSecretsClient() #type: ignore
        firebase_creds_json = user_secrets.get_secret("FIREBASE_CREDENTIALS")
    else:
        firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
    
    if not firebase_creds_json:
        raise ValueError("Firebase credentials not found. Ensure 'FIREBASE_CREDENTIALS' is set.")
    
    firebase_creds_dict = json.loads(firebase_creds_json)
except (json.JSONDecodeError, ValueError) as e:
    print(f"Error: Failed to load Firebase credentials. Detail: {e}")
    exit()
except Exception as e:
    print(f"Error during Firebase credential setup: {e}")
    exit()

# Initialize Firebase Admin SDK (only once per application instance)
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(firebase_creds_dict)
        firebase_admin.initialize_app(cred)
        print("Firebase service initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase service: {e}")
        exit()

db = firestore.client()
FATWA_COLLECTION_NAME = 'fatwa_embeddings_fixed_final'
fatwa_collection = db.collection(FATWA_COLLECTION_NAME)
halal_status_cache = db.collection('halal_status_cache')

# --- RAG Search Function ---
async def search_fatwa_embeddings(query_embedding: list, limit: int = 5) -> list:
    """
    Searches for the most relevant fatwa chunks in Firestore based on a query embedding.
    """
    relevant_chunks = []
    try:
        docs = fatwa_collection.stream()
        
        all_embeddings = []
        all_texts = []
        all_metadata = []

        for doc in docs:
            data = doc.to_dict()
            if 'embedding' in data and 'chunk_text' in data:
                all_embeddings.append(np.array(data['embedding'])) 
                all_texts.append(data['chunk_text'])
                all_metadata.append({
                    'filename': data.get('filename'),
                    'source': data.get('source'),
                    'chunk_id': data.get('chunk_id')
                })
        
        if not all_embeddings:
            print("No embeddings found in Firestore collection.")
            return []

        query_embedding_np = np.array(query_embedding).reshape(1, -1)
        
        similarities = cosine_similarity(query_embedding_np, np.array(all_embeddings))[0]
        sorted_indices = similarities.argsort()[::-1] 
        
        for i in sorted_indices[:limit]:
            relevant_chunks.append({
                "text": all_texts[i],
                "similarity": similarities[i],
                "metadata": all_metadata[i]
            })
            
    except firebase_exceptions.FirebaseError as e:
        print(f"Firebase error during search: {e}")
    except Exception as e:
        print(f"Error during embedding search: {e}")
    
    return relevant_chunks

# --- HalalScan Cache Functions ---
async def save_halal_status(task_id: str, status_data: dict):
    """
    Saves the HalalScan result to a Firestore cache collection.
    """
    try:
        doc_ref = halal_status_cache.document(task_id)
        await doc_ref.set(status_data) #type: ignore
        return True
    except Exception as e:
        print(f"Error saving halal status to Firestore for task {task_id}: {e}")
        return False

async def get_halal_status_by_id(task_id: str):
    """
    Retrieves the HalalScan result from Firestore cache by task ID.
    """
    try:
        doc_ref = halal_status_cache.document(task_id)
        doc = await doc_ref.get() #type: ignore
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"Error retrieving halal status from Firestore for task {task_id}: {e}")
        return None

