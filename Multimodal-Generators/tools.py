import os
from ibm_watsonx_ai import Credentials, APIClient
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from gtts import gTTS
from openai import OpenAI

def get_llm_model():
    """Initializes and returns the foundation model for text generation."""
    credentials = Credentials(
        url="https://us-south.ml.cloud.ibm.com",
    )
    project_id = "skills-network"
    model_id = 'meta-llama/llama-3-2-11b-vision-instruct'
    
    params = {
        GenParams.DECODING_METHOD: "greedy",
        GenParams.MAX_NEW_TOKENS: 1000,
    }
    
    return ModelInference(
        model_id=model_id,
        credentials=credentials,
        project_id=project_id,
        params=params,
    )

def generate_story(topic):
    """Generates an educational story based on a given topic."""
    model = get_llm_model()
    prompt = f"""Write an engaging and educational story about {topic} for beginners. 
            Use simple and clear language to explain basic concepts. 
            Include interesting facts and keep it friendly and encouraging. 
            The story should be around 200-300 words and end with a brief summary of what we learned. 
            Make it perfect for someone just starting to learn about this topic."""
    
    response = model.generate_text(prompt=prompt)
    return response

def text_to_audio(text, output_file="story.mp3"):
    """Converts text to an audio file."""
    tts = gTTS(text)
    tts.save(output_file)
    print(f"Audio saved to {output_file}")

def generate_image(prompt, model="dall-e-3", size="1024x1024", quality="standard"):
    """Generates an image using OpenAI's DALL-E models."""
    client = OpenAI()
    response = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
    )
    return response.data[0].url
