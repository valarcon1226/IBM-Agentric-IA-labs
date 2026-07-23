from tools import generate_story, text_to_audio, generate_image

def main():
    print("Welcome to Multimodal AI Generators!")
    
    # 1. Generate Story
    topic = "the life cycle of butterflies"
    print(f"\nGenerating story about: {topic}...")
    
    try:
        story = generate_story(topic)
        print("\n--- Generated Story ---")
        print(story)
        print("-----------------------\n")
        
        # 2. Convert to Audio
        print("Generating audio narration...")
        text_to_audio(story, "butterfly_story.mp3")
        
    except Exception as e:
        print(f"Failed to generate story or audio: {e}")
        
    # 3. Generate Image
    print("\nGenerating illustration...")
    image_prompt = f"A beautiful educational illustration showing {topic}"
    try:
        image_url = generate_image(image_prompt)
        print(f"Image generated successfully! View it here: {image_url}")
    except Exception as e:
        print(f"Failed to generate image: {e}")
        print("Note: OpenAI API key may not be configured properly.")

if __name__ == '__main__':
    main()
