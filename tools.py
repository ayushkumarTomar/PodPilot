from langchain_community.tools import YouTubeSearchTool
from langchain_core.tools import tool
import subprocess

import requests
from subtitle_fix import shift_subtitles_to_zero_start , srt_to_ass

yt_tool = YouTubeSearchTool()
import glob
from typing import Any
from pydantic import BaseModel, Field
class TrimMediaInput(BaseModel):
    input_file: str = Field(...)
    output_file: str = Field(...)
    start_time: str = Field(...)
    end_time: str = Field(...)
import json
import os

@tool
def report_error(error: str) -> None:
    """
    Report errors during processing.

    Args:
        error (str): The error message to report.

    This function is intended to help with debugging by logging or 
    notifying about runtime issues.
    """
    print("Reporting error ::", error)

@tool
def get_youtube_object(video_id: str) -> dict:
    """
    
    Fetches the description 
    Args:
        video_id(str) : The youtube Id of the object 
    Returns:
        return the description of the video 
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    cookies_path = "./cookie.txt"

    cmd = [
        "yt-dlp",
        "--cookies", cookies_path,
        "--skip-download",
        "--quiet",
        "--no-warnings",
        "--print-json",
        video_url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        subtitles = info.get("automatic_captions", {})
        lang_code = next((code for code in subtitles if code.endswith("-orig")), None)
        return info.get('description') , lang_code
    except subprocess.CalledProcessError as e:
        send_video.invoke("COOKIE EXPIRED")
        print(f"[ERROR] yt-dlp failed: {e.stderr}")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON output: {e}")

    
    return None


from pydantic import BaseModel, Field


def trim_media(input: TrimMediaInput):
    """
    Trim a media file (audio/video) using FFmpeg.

    Args:
        input_file (str): Full path to the original media file.
        output_file (str): Desired path for the trimmed output file.
        start_time (str): Trim start time ('HH:MM:SS' or seconds).
        end_time (str): Trim end time ('HH:MM:SS' or seconds).

    The function uses FFmpeg to extract a specific portion of the file without re-encoding.
    """

    def to_seconds(t):
        if isinstance(t, (int, float)):
            return float(t)
        parts = [float(p) for p in t.split(':')]
        if len(parts) == 3:
            return parts[0]*3600 + parts[1]*60 + parts[2]
        elif len(parts) == 2:
            return parts[0]*60 + parts[1]
        else:
            return parts[0]

    start_sec = to_seconds(input["start_time"])
    end_sec = to_seconds(input["end_time"])
    duration = end_sec - start_sec

    command = [
        'ffmpeg',
        '-y',
        '-ss', str(start_sec),
        '-i', input["input_file"],
        '-t', str(duration),
        '-c', 'copy',
        input["output_file"]
    ]

    try:
        subprocess.run(command, check=True)
        print(f"Trimmed media saved to {input['output_file']}")
    except subprocess.CalledProcessError as e:
        print("Error trimming media:", e)





def youtube_tool(video_id:str, lang:str, output_path: str = "./data/current_podcast.mp4"):
    """
    Downloads a YouTube video using yt-dlp subprocess and a cookie file.

    Args:
        info (Any): The video info object or video ID/URL.
        lang (str) : Subtitle code
        output_path (str): Path to save the downloaded file.
    """
    # Determine video URL
    video_url = "https://youtube.com/watch?v="+video_id

    if not video_url:
        raise ValueError("Invalid video info or missing URL.")

    cmd = [
        "yt-dlp",
        "--cookies", "./cookie.txt",
        "-f", "best",
        "--write-auto-sub",
        "--sub-format" , "srt",
        "--sub-langs" , lang,
        '-o' ,"./data/current_podcast.%(ext)s",
        video_url
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"[SUCCESS] Video downloaded to: {output_path}")
    except subprocess.CalledProcessError as e:
        send_video.invoke("COOKIE EXPIRED")
        print(f"[ERROR] Download failed:\n{e}")
    filepath = glob.glob('./data/current_podcast*.srt')[0]
    return filepath


def convert_and_add_captions(input_video: str, srt_file: str, output_video: str):
    """
    Convert a video to 9:16 aspect ratio, scale to HD, and burn subtitles.

    Args:
        input_video (str): Path to the input video file.
        srt_file (str): Path to the subtitle (.srt) file to burn in.
        output_video (str): Output filename for the final video.

    This function:
    - Crops to 9:16 portrait ratio.
    - Scales to 720x1280.
    - Hardcodes (burns) subtitles into the video using FFmpeg.
    """


    d = open(srt_file , "r" , encoding='utf-8')
    data_subtitle = d.read()
    shifted_subtitles = shift_subtitles_to_zero_start(data_subtitle)

    open(srt_file , 'w+' , encoding='utf-8').write(shifted_subtitles)
    srt_to_ass(srt_file , srt_file+"-.ass")

    filter_chain = (
    f"subtitles={srt_file+'-.ass'},"
    "split[original][copy];"
    "[copy]scale=-1:ih*(16/9)*(16/9),"
    "crop=w=ih*9/16,"
    "gblur=sigma=20[blurred];"
    "[blurred][original]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2"
)
    
    command = [
    "ffmpeg",
    "-i", input_video,
    "-vf", filter_chain,
    "-y",  # Overwrite output if it exists
    output_video
]

    print("Running FFmpeg command:")
    print(" ".join(command))

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if process.returncode == 0:
        print(f"Successfully created {output_video}")
    else:
        print("Error running FFmpeg:")
        print(process.stderr)

def print_green(text):
    print(f"\033[92m{text}\033[0m")  # Bright Green

def print_yellow(text):
    print(f"\033[93m{text}\033[0m")  # Bright Yellow


def upload_video(file_path , metadata ):
    """
    Uploads the video yo YouTube

    Args:
        file_path: The path of the file to upload
        metadata : dict of the metadata to upload 
        {
            title:"Title of the video",
            description:"Description of the video",
            privacyStatus:"public",
            keywords=["surfing" , "second"],
            category = "22"
        }
    
    """
    command = [
    "python",
    "yt_upload.py",
    "--file" , file_path  ,
    "--title",  metadata['title'],
    "--privacyStatus" , "public",
    "--keywords" , ",".join(metadata["keywords"]),
    "--category", "27",
    "--description" , metadata["description"]
    ]

    print(" ".join(command))

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if process.returncode == 0:
        print_green(f"Successfully uploaded {file_path}")
    else:
        print("Error running FFmpeg:")
        print(process.stderr)
        send_video.invoke("YT UPLOAD EXPIRED")



@tool
def send_video(text:str):
    """
    This tool sends message to the developers's telegram
    Args:
        text - The message to send to developer
    """
    token = '5994700267:AAGRpV-0LN4dh19i3jrzzHpCHmYXFFEoW68'
    chatId = '1152614079'

    send_msg_url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = {
        "chat_id": chatId,
        "text" : text
    }

    requests.post(send_msg_url, data=data)

if __name__ == '__main__':
   
    obj = get_youtube_object.invoke("r8pDXO6zRUg")
    print(youtube_tool(obj))
   