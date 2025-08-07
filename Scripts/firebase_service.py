import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import exceptions as firebase_exceptions
import json
import os
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    from kaggle_secrets import UserSecretsClient
    ON_KAGGLE = True
except ImportError:
    ON_KAGGLE = False
    from dotenv import load_dotenv
    load_dotenv()


try:
    if ON_KAGGLE:
        user_secrets = UserSecretsClient()
        firebase_creds_json = user_secrets.get_secret("Firebase Credentials")
    else:
        firebase_creds_json = os.getenv("Firebase Credentials")
    
    if not firebase_creds_json:
        raise ValueError("Firebase credentials not found. Ensure 'Firebase Credentials' is set.")
    
    firebase_creds_dict = json.loads(firebase_creds_json)
except (json.JSONDecodeError, ValueError) as e:
    print(f"Error: Failed to load Firebase credentials. Detail: {e}")
    exit()
except Exception as e:
    print(f"Error during Firebase credential setup: {e}")
    exit()

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_creds_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase service initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase service: {e}")
    exit()


FATWA_COLLECTION_NAME = 'fatwa_embeddings_fixed_final'
fatwa_collection = db.collection(FATWA_COLLECTION_NAME)


async def search_fatwa_embeddings(query_embedding: list, limit: int = 5) -> list:
    """
    Searches for the most relevant fatwa chunks in Firestore based on a query embedding.

    Args:
        query_embedding (list): The embedding vector of the user's query.
        limit (int): The maximum number of relevant chunks to retrieve.

    Returns:
        list: A list of dictionaries, where each dictionary contains:
              - "text": The original chunk text.
              - "similarity": The cosine similarity score with the query.
              - "metadata": Dictionary containing filename, source, and chunk_id.

    Note: This is a brute-force similarity search, which means it fetches all
    embeddings from Firestore and calculates similarity locally. This approach
    is suitable for small to medium-sized datasets (thousands of embeddings).
    For very large datasets (millions of embeddings), a dedicated vector database
    (like Pinecone, Weaviate, or specialized Firestore vector search if available)
    or a more optimized search strategy would be required for performance.
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