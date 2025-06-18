
from langchain_core.documents import Document
import pysrt
import os
def chunk_srt_by_chars(srt_path, max_chars=70000):
    subs = pysrt.open(srt_path)
    chunks = []
    current_chunk = []
    current_char_count = 0

    for sub in subs:
        entry_text = f"{sub.index}\n{sub.start} --> {sub.end}\n{sub.text}\n\n"
        if current_char_count + len(entry_text) > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_char_count = 0
        current_chunk.append(sub)
        current_char_count += len(entry_text)

    if current_chunk:
        chunks.append(current_chunk)

    # Prepare clean export format
    result = []
    for i, chunk in enumerate(chunks):
        chunk_text = "\n".join(
            f"{sub.index}\n{sub.start} --> {sub.end}\n{sub.text}" for sub in chunk
        )
        result.append({
            "chunk_index": i,
            "start_time": str(chunk[0].start),
            "end_time": str(chunk[-1].end),
            "srt_text": chunk_text
        })

    return result

def extract_srt_segment(srt_path, start_time_str, end_time_str):
    """
    Extracts subtitles between start_time and end_time from an SRT file.

    :param srt_path: Path to the .srt file
    :param start_time_str: Start timestamp as string, e.g., "00:12:00,000"
    :param end_time_str: End timestamp as string, e.g., "00:15:30,000"
    :return: List of pysrt.SubRipItem objects within the range
    """
    subs = pysrt.open(srt_path)
    start = pysrt.SubRipTime.from_string(start_time_str)
    end = pysrt.SubRipTime.from_string(end_time_str)

    selected = [sub for sub in subs if start <= sub.start <= end]

    return selected
def save_srt(subs, output_path):
    """
    Saves a list of pysrt.SubRipItem objects to a new .srt file.

    :param subs: List of subtitle items
    :param output_path: Output path to save .srt file
    """
    subrip_file = pysrt.SubRipFile(items=subs)
    subrip_file.clean_indexes()
    subrip_file.save(output_path, encoding='utf-8')

transcription_segments = [
    {'text': "Ladies and gentlemen, he's one of the", 'duration': 2.96, 'offset': 0.08, 'lang': 'en'},
    {'text': 'most successful artists in the world. Is', 'duration': 4.081, 'offset': 1.439, 'lang': 'en'},
    {'text': "my tower tower. Let's say a couple", 'duration': 4.719, 'offset': 3.04, 'lang': 'en'},
    {'text': "artists they make songs like I'm out in", 'duration': 6.159, 'offset': 5.52, 'lang': 'en'},
    {'text': "the club. I'm by They're not even out to", 'duration': 5.84, 'offset': 7.759, 'lang': 'en'},
    {'text': "the wild wild west", 'duration': 2.0, 'offset': 14.0, 'lang': 'en'},
    {'text': "where the sun always shines", 'duration': 3.5, 'offset': 16.5, 'lang': 'en'},
    {'text': "and the cowboys ride freely", 'duration': 4.0, 'offset': 20.0, 'lang': 'en'},
]

def chunk_transcription_data(segments, max_chunk_chars=200):
    """
    Chunks transcription data by combining complete original segments,
    dynamically updating metadata (offset, duration) for each chunk.

    Args:
        segments (list): A list of dictionaries, each representing a speech segment.
        max_chunk_chars (int): The maximum character limit for each generated chunk.

    Returns:
        list: A list of LangChain Document objects, each representing a chunk
              with updated metadata.
    """
    chunks = []
    current_chunk_text = []
    current_chunk_start_offset = None
    current_chunk_end_offset = None
    current_chunk_lang = None # Assuming language is consistent or you handle it

    for segment in segments:
        segment_text = segment['text']
        segment_duration = segment['duration']
        segment_offset = segment['offset']
        segment_lang = segment['lang']

        # If adding this segment exceeds the max_chunk_chars,
        # or if there's a language change (if you want to chunk by lang)
        # then finalize the current chunk and start a new one.
        # We add 1 for the space that will be inserted when joining.
        if (len(" ".join(current_chunk_text)) + len(segment_text) + (1 if current_chunk_text else 0) > max_chunk_chars) \
           or (current_chunk_lang is not None and current_chunk_lang != segment_lang):
            if current_chunk_text: # Only create a chunk if there's text
                chunk_content = " ".join(current_chunk_text)
                chunks.append(
                    Document(
                        page_content=chunk_content,
                        metadata={
                            "source_type": "audio_transcription",
                            "original_audio_start_offset": current_chunk_start_offset,
                            "original_audio_end_offset": current_chunk_end_offset,
                            "language": current_chunk_lang,
                            "num_original_segments": len(current_chunk_text) # Optional: count original segments
                        }
                    )
                )
                # Reset for the new chunk
                current_chunk_text = []
                current_chunk_start_offset = None
                current_chunk_end_offset = None
                current_chunk_lang = None

        # Add the current segment to the accumulating chunk
        current_chunk_text.append(segment_text)

        # Update metadata for the current accumulating chunk
        if current_chunk_start_offset is None:
            current_chunk_start_offset = segment_offset
        current_chunk_end_offset = segment_offset + segment_duration # Always update to the end of the last segment added
        current_chunk_lang = segment_lang # Assuming consistent for a chunk, or you decide how to handle mixed lang


    # Add the last chunk if any text remains
    if current_chunk_text:
        chunk_content = " ".join(current_chunk_text)
        chunks.append(
            Document(
                page_content=chunk_content,
                metadata={
                    "source_type": "audio_transcription",
                    "original_audio_start_offset": current_chunk_start_offset,
                    "original_audio_end_offset": current_chunk_end_offset,
                    "language": current_chunk_lang,
                    "num_original_segments": len(current_chunk_text)
                }
            )
        )
    return chunks


if __name__ == '__main__':
    print(chunk_srt_by_chars('./ts (a.en).srt')[0])

    clip_subs = extract_srt_segment('./ts (a.en).srt' , "00:03:31,920" , "00:05:31,039")

    save_srt(clip_subs, "clip_subs.srt")
