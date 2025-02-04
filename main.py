import argparse
import pathlib
import random
import json
import moviepy.editor as mp
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

from better_profanity import profanity
# Custom replacements for bad words
FAMILY_FRIENDLY_REPLACEMENTS = {
    "damn": "darn",
    "hell": "heck",
    "shit": "poop",
    "fuck": "fudge",
    "bitch": "witch",
    "whore": "witch",
    "asshole": "meanie",
    "bastard": "rascal"
}

__VERSION__ = "0.0.1"
CONFIG_FILE = "assets/config.json"

def load_config():
    """ Load configuration from JSON file. """
    if pathlib.Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def get_config_value(args, config, key, required=True):
    """ Get a value from command-line args or fallback to JSON config. """
    value = getattr(args, key, None)
    if value is None:
        value = config.get(key)
    if required and value is None:
        print(f"Error: Missing required parameter '{key}'. Provide it via CLI or {CONFIG_FILE}.")
        exit(1)
    return value

def filter_text(text: str) -> str:
    """ Replaces bad words with family-friendly alternatives. """
    profanity.load_censor_words()
    words = text.split()
    
    # Replace bad words with friendly versions
    filtered_words = [
        FAMILY_FRIENDLY_REPLACEMENTS.get(word.lower(), word) 
        if word.lower() not in FAMILY_FRIENDLY_REPLACEMENTS 
        else FAMILY_FRIENDLY_REPLACEMENTS[word.lower()]
        for word in words
    ]
    
    return " ".join(filtered_words)

def get_input_text(input_file: pathlib.Path) -> str:
    # Read input text file
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            text = file.read().strip()
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        exit(1)
        
    # Filter text
    text = filter_text(text)

    return text

def generate_speech(api_key_: str, text_: str, output_audio: str, voice_id_: str) -> None:
    """ Uses ElevenLabs SDK to generate speech and save it as an MP3 file. """
    client = ElevenLabs(
        api_key=api_key_,
    )
    audio = client.text_to_speech.convert(
        text=text_,
        voice_id=voice_id_,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    
    # Writing the audio to a file
    with open(output_audio, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)
    
    print(f"Audio saved: {output_audio}")

def pick_random_video(folder: pathlib.Path) -> pathlib.Path:
    """ Selects a random video file from the folder. """
    video_files = list(folder.glob("*.mp4"))
    if not video_files:
        print("No videos found in background folder!")
        exit(1)
    return random.choice(video_files)

def generate_subtitle_timestamps(text: str, audio_duration: float):
    """ Generate subtitles that display a maximum of two words at a time. """
    words = text.split()
    if not words:
        print("Error: Input text is empty.")
        return []
    
    subtitle_parts = []
    word_groups = [words[i:i+2] for i in range(0, len(words), 2)]  # Group words in pairs
    
    segment_duration = audio_duration / len(word_groups)  # Evenly distribute timing
    
    for i, group in enumerate(word_groups):
        start_time = i * segment_duration
        end_time = min((i + 1) * segment_duration, audio_duration)
        subtitle_parts.append({
            'text': ' '.join(group),
            'start_time': start_time,
            'end_time': end_time
        })
    
    return subtitle_parts

def create_video_with_subtitles(audio_file: pathlib.Path, video_file: pathlib.Path, output_file: pathlib.Path, text: str):
    """ Combines video and audio, fills the screen, and adds centered subtitles. """
    video = VideoFileClip(str(video_file))
    audio = AudioFileClip(str(audio_file))

    video = video.set_duration(audio.duration)
    target_width, target_height = 1080, 1920
    video = video.resize(height=target_height)
    video = video.crop(x_center=video.size[0] / 2, y_center=video.size[1] / 2, width=target_width, height=target_height)

    subtitle_parts = generate_subtitle_timestamps(text, audio.duration)
    
    subtitle_clips = []
    for subtitle in subtitle_parts:
        subtitle_clip = TextClip(subtitle['text'], font='Verdana', fontsize=100, color='white', 
                                 stroke_color='black', stroke_width=2, align='center', method='caption',
                                 size=(video.size[0], None))
        subtitle_clip = subtitle_clip.set_position(('center', 'center')).set_start(subtitle['start_time']).set_duration(subtitle['end_time'] - subtitle['start_time'])
        subtitle_clip = subtitle_clip.fadein(0.0).fadeout(0.0)  # Smooth transitions
        subtitle_clips.append(subtitle_clip)

    final_video = CompositeVideoClip([video] + subtitle_clips).set_audio(audio)
    final_video.write_videofile(str(output_file), codec="libx264", fps=60)
    
    print(f"Output saved: {output_file}")

def main() -> None:
    """ Main function to process input, generate speech, and create video. """
    config = load_config()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description=f'BrainRot Generator {__VERSION__}')
    parser.add_argument('--elevenlabs-api-key', type=str, help="API Key for ElevenLabs")
    parser.add_argument('--voice-id', type=str, help="Voice ID for ElevenLabs")
    parser.add_argument('--background-folder', type=str, help="Folder with background videos")
    parser.add_argument('--input', type=str, help="Input text file")
    parser.add_argument('--output', type=str, help="Output video file")
    args = parser.parse_args()

    # Get values from CLI or fallback to JSON
    api_key = get_config_value(args, config, "elevenlabs-api-key")
    voice_id = get_config_value(args, config, "voice-id")
    background_folder = get_config_value(args, config, "background-folder")
    input_file = get_config_value(args, config, "input")
    output_file = get_config_value(args, config, "output")

    # Add suffix if not present
    output_path = pathlib.Path(output_file)
    if not output_path.suffix:
        output_path = output_path.with_suffix(".mp4")
    
    output_file_path = pathlib.Path(output_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensures the directory exists

    # Get input text
    text = get_input_text(pathlib.Path(input_file))

    # Generate speech audio
    audio_path = pathlib.Path(output_path).with_suffix(".mp3")
    #generate_speech(api_key, text, str(audio_path), voice_id)

    # Pick a random background video
    background_video = pick_random_video(pathlib.Path(background_folder))

    # Create final video
    create_video_with_subtitles(audio_path, background_video, output_path, text)

if __name__ == "__main__":
    main()