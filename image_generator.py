import os
import urllib.parse
import requests

def generate_image(prompt: str, output_path: str = "output/raw_image.png") -> str:
    """
    Generates a 1080x1080 image using Pollinations.ai API based on the prompt.
    Saves the image to output_path and returns the local file path.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    encoded_prompt = urllib.parse.quote(f"{prompt}, high quality, cinematic, 8k, detailed")
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true&seed=42"

    print(f"Generating image via Pollinations.ai...")
    response = requests.get(image_url, timeout=60)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"Image successfully saved to {output_path}")
    return output_path

if __name__ == "__main__":
    test_prompt = "A glowing golden honey jar inside an ancient Egyptian pyramid tomb, 3d render"
    generate_image(test_prompt, "output/test_image.png")
