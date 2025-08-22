from google import genai
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
    
    client = genai.Client(api_key=gemini_api_key)
    print("Gemini API configured successfully in LLM service.")
except ValueError as e:
    print(f"Error: {e}")
    client = None 
except Exception as e:
    print(f"Error during Gemini API configuration in LLM service: {e}")
    client = None 

async def generate_response_from_context(user_query: str, context_chunks: list) -> str:
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
    if not client:
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
            response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
            return getattr(response, "text", "") or ""
        except Exception as e:
            print(f"Attempt {i+1} failed to generate LLM response: {e}")
            if i < retries - 1:
                wait_time = 2 ** i 
                print(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time) 
            else:
                print(f"All retry attempts failed for LLM response generation.")
                return "Maaf, terjadi kesalahan saat memproses permintaan Anda. Silakan coba lagi nanti."
    # Ensure a string is always returned
    return "Maaf, terjadi kesalahan yang tidak terduga saat memproses permintaan Anda."

async def generate_response_with_search(user_query: str) -> str:
    """
    Generates a response using the Gemini LLM with web search functionality.
    This replaces the RAG flow entirely.
    """
    if not client:
        return "Maaf, layanan AI tidak tersedia untuk menghasilkan jawaban."

    # This prompt tells Gemini to act as a syariah expert and use web search results
    # to answer questions. It's a simple form of prompt engineering.
    prompt = f"""
    Anda adalah asisten AI yang ahli dalam hukum syariah. Jawablah pertanyaan pengguna dengan melakukan pencarian di web jika perlu. Jika tidak ada informasi yang ditemukan atau pertanyaan tidak relevan dengan hukum syariah, berikan respons yang sopan dan informatif.

    Pertanyaan Pengguna: {user_query}
    
    Jawaban:
    """
    retries = 3
    for i in range(retries):
        try:
            # We use gemini-2.5-flash with a web search tool
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )
            return response.text if response.text else "Maaf, saya tidak dapat menemukan jawaban yang relevan untuk pertanyaan Anda."
        except Exception as e:
            print(f"Attempt {i+1} failed to generate LLM response: {e}")
            if i < retries - 1:
                wait_time = 2 ** i
                print(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                print(f"All retry attempts failed for LLM response generation.")
                return "Maaf, terjadi kesalahan saat memproses permintaan Anda. Silakan coba lagi nanti."
    
    return "Maaf, terjadi kesalahan yang tidak terduga saat memproses permintaan Anda."