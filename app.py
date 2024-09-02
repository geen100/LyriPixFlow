import os
import requests
from flask import Flask, render_template, request
from dotenv import load_dotenv
from openai import OpenAI
import time

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=api_key)

# Suno Cookie
suno_cookie = os.getenv('SUNO_COOKIE')
app = Flask(__name__)


genres = ["pop", "rock", "jazz", "classical", "hiphop", "electronic", "reggae", "country", "blues", "metal"]

base_url = os.getenv('BASE_URL')
sheetdb_api_url = os.getenv('SHEETDB_API_URL')

def generate_audio_by_prompt(payload):
    url = f"{base_url}/api/generate"
    response = requests.post(url, json=payload, headers={'Content-Type': 'application/json', 'Cookie': suno_cookie})
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
    except ValueError as json_err:
        print(f"JSON decode error: {json_err}")
    return None

def get_audio_information(audio_id):
    url = f"{base_url}/api/get?ids={audio_id}"
    response = requests.get(url)
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
    except ValueError as json_err:
        print(f"JSON decode error: {json_err}")
    return None

def save_to_sheetdb(data):
    response = requests.post(sheetdb_api_url, json=data)
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
    except ValueError as json_err:
        print(f"JSON decode error: {json_err}")
    return None

def fetch_all_from_sheetdb():
    response = requests.get(sheetdb_api_url)
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
    except ValueError as json_err:
        print(f"JSON decode error: {json_err}")
    return None

@app.route('/')
def home():
    return render_template('index.html', genres=genres)

@app.route('/generate_story', methods=['POST'])
def generate_story():
    user_input = request.form['user_input']
    genre = request.form['genre']

    # Generate lyrics using OpenAI API
    try:
        response = client.chat.completions.create(model="gpt-4",
        messages=[
            {"role": "system", "content": "Create song lyrics without using phrases like 'Verse' or 'Chorus'. Make sure the lyrics are complete and within the max tokens limit."},
            {"role": "user", "content": user_input}
        ],
        max_tokens=200)
        print(response)  # Output the entire response for checking
        generated_story = response.choices[0].message.content.strip()

        # Limit the length of the generated story for Suno API
        if len(generated_story) > 1000:
            generated_story = generated_story[:1000]

    except Exception as e:
        print(f"Error generating story: {e}")
        return render_template('index.html', error="Error generating story", genres=genres)

    # Generate image using DALL-E
    try:
        dalle_response = client.images.generate(prompt=generated_story,
        n=1,
        size="512x512")
        generated_image_url = dalle_response.data[0].url
    except Exception as e:
        print(f"Error generating image: {e}")
        return render_template('index.html', error="Error generating image", genres=genres)

    # Generate music using Suno API
    try:
        payload = {
            "prompt": generated_story,  # Generated lyrics as prompt
            "make_instrumental": False,
            "wait_audio": False
        }
        print(f"Sending data to Suno API: {payload}")
        suno_response = generate_audio_by_prompt(payload)
        print(f"Suno API response: {suno_response}")

        if suno_response and isinstance(suno_response, list) and len(suno_response) > 0:
            audio_id = suno_response[0]['id']
            generated_music_url = None
            for _ in range(60):  # 最大60回試行（5分）
                data = get_audio_information(audio_id)
                if data and isinstance(data, list) and len(data) > 0:
                    status = data[0].get("status", "")
                    print(f"Status of audio generation: {status}")
                    if status in ['complete', 'streaming']:
                        generated_music_url = data[0].get('audio_url', '')
                        created_at = data[0].get('created_at', '')
                        break
                time.sleep(5)
        else:
            print(f"Error from Suno API: {suno_response}")
            generated_music_url = None
    except Exception as e:
        print(f"Error contacting Suno API: {e}")
        return render_template('index.html', error="Error contacting Suno API", genres=genres)

    # Save to SheetDB
    sheetdb_data = {
        "id": audio_id,
        "keyword": user_input,
        "lyrics": generated_story,
        "image": generated_image_url,
        "music": generated_music_url,
        "days": created_at
    }
    save_response = save_to_sheetdb({"data": [sheetdb_data]})
    print(f"SheetDB save response: {save_response}")

    return render_template('generate_story.html', user_input=user_input, generated_story=generated_story, generated_image_url=generated_image_url, generated_music_url=generated_music_url)

@app.route('/history')
def history():
    data = fetch_all_from_sheetdb()
    if data:
        history_data = data
    else:
        history_data = []
    return render_template('history.html', history_data=history_data)

if __name__ == '__main__':
    app.run(debug=True)
