import google.generativeai as genai
import os
import asyncio 
import time 

try:
    from kaggle_secrets import UserSecretsClient #type: ignore
    ON_KAGGLE = True
except ImportError:
    ON_KAGGLE = False
    from dotenv import load_dotenv
    load_dotenv() 

try:
    if ON_KAGGLE:
        user_secrets = UserSecretsClient() #type: ignore
        gemini_api_key = user_secrets.get_secret("GEMINI_API_KEY")
    else:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not found. Ensure 'GEMINI_API_KEY' is set.")
    
    genai.configure(api_key=gemini_api_key) #type: ignore
    llm_model = genai.GenerativeModel(model_name='gemini-2.5-flash') #type: ignore
    print("Gemini API configured successfully in LLM service.")
except ValueError as e:
    print(f"Error: {e}")
    llm_model = None 
except Exception as e:
    print(f"Error during Gemini API configuration in LLM service: {e}")
    llm_model = None 

async def generate_response_from_context(user_query: str, context_chunks: list) -> str: #type: ignore
    """
    Generates a response using the Gemini LLM based on the user's query and provided fatwa context.

    Args:
        user_query (str): The original question from the user.
        context_chunks (list): A list of dictionaries, where each dictionary contains
                                the 'text' of a relevant fatwa chunk.

    Returns:
        str: The AI-generated response.
             Returns a fallback message if the LLM model is not available or an error occurs.
    """
    if not llm_model:
        return "Maaf, layanan AI tidak tersedia untuk menghasilkan jawaban."

    context_text = "\n\n".join([chunk['text'] for chunk in context_chunks])
    
    prompt = f"""
    Anda adalah asisten AI yang ahli dalam hukum syariah berdasarkan fatwa MUI.
    Jawablah pertanyaan berikut HANYA berdasarkan konteks fatwa yang saya berikan.
    Jika informasi tidak ditemukan dalam konteks, katakan bahwa Anda tidak dapat menjawabnya.
    Jangan mengarang jawaban.
    Sertakan nomor fatwa atau bagian fatwa yang menjadi dasar jawaban Anda jika memungkinkan.

    Pertanyaan Pengguna: {user_query}

    Konteks Fatwa:
    {context_text}

    Jawaban:
    """
    max_prompt_chars = 4000000 
    
    if len(prompt) > max_prompt_chars:
        return "Maaf, pertanyaan dan konteks yang diberikan terlalu panjang untuk diproses."
    retries = 3
    for i in range(retries):
        try:
            response = await llm_model.generate_content(prompt) #type: ignore
            return response.text
        except Exception as e:
            print(f"Attempt {i+1} failed to generate LLM response: {e}")
            if i < retries - 1:
                wait_time = 2 ** i 
                print(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time) 
            else:
                print(f"All retry attempts failed for LLM response generation.")
                return "Maaf, terjadi kesalahan saat memproses permintaan Anda. Silakan coba lagi nanti."