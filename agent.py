import os
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts import moments_template , podcast_selector_prompt
from langgraph.graph import END, StateGraph
from typing import List
from schema import MomentsList , Moment , Best_Podcast
from state import AgentState
from dotenv import load_dotenv
from copy import deepcopy
from tools import yt_tool ,send_video , upload_video , report_error , youtube_tool , trim_media , get_youtube_object , convert_and_add_captions , print_green , print_yellow
from constants import *
from chunking import chunk_srt_by_chars , save_srt , extract_srt_segment
import json
import time
import shutil

assert os.getenv("GOOGLE_API_KEY"), "Missing GOOGLE_API_KEY in .env"
assert os.getenv("GOOGLE_PROJECT_ID") , "Missing GOOGLE_PROJECT_ID in .env"

load_dotenv()
model_name = "gemini-2.0-flash"

llm = ChatGoogleGenerativeAI(
    model=model_name,
    model_kwargs = {
        "project_id":os.getenv("GOOGLE_PROJECT_ID"),

        # CUSTOMIZE AGENT ARGS TO GET THE BEST OUTPUT FOR YOUR NEEDS
        # "temperature": 0.7,           
        # "top_p": 0.9,
        # "top_k": 40,
        # "max_output_tokens": 1024
    }
    
)

youtube_filter_codes = {
    "week" : "EgIIAw",
    "month" : "EgQIBBAB"
}
def search_podcasts(state:AgentState):
    """
    Searches for trending podcasts on YouTube.
    """
    print_yellow("GETTING PODCASTS .....")
    if state['retry'] !=None:
        podcast_list = yt_tool.invoke(f"podcast,15,{youtube_filter_codes[state['retry']]}")
    else:
        podcast_list = yt_tool.invoke(f"podcast,15")
        state['retry'] = None

    podcast_list = json.loads(podcast_list)

    try:
        for podcast in podcast_list['videos']:
            description , lang = get_youtube_object.invoke(podcast['id'])
            del podcast['thumbnails']
            del podcast['long_desc']
            podcast['description'] = description
            # podcast['youtube_object'] = youtube_object
            podcast['subtitle_lang'] = lang
    except Exception as e:
        print(f"SKIPPING {podcast['id']} due to {e}")
    return {
        "podcast_list":podcast_list['videos']
    }


def get_best_podcast_from_llm(state:AgentState):
    """
    Filters the best podcast out of the trending ones.
    """
    print_green("FETCHING BEST PODCASTS .....")
    fp = open('burnt_podcasts.json' , 'r')
    excluded_list = json.load(fp)
    fp.close()

    chain = podcast_selector_prompt | llm.with_structured_output(Best_Podcast)
    filtered_podcast_list = [
    {k: v for k, v in podcast.items() if k != 'subtitle_lang'}
    for podcast in state["podcast_list"]
]
    result = chain.invoke({"podcast_list":filtered_podcast_list , "excluded_list":excluded_list})
    if result.selected == False:
        state['retry'] = 'month' if state['retry']==None else 'week'
    podcast_metadata = next((p for p in state["podcast_list"] if p['id'] == result.video_id), None)

    return {
        "podcast" : {
            "podcast_title" : podcast_metadata["title"],
            "podcast_description" : podcast_metadata["description"],
            "transcript" : [] ,
            "video_id" : podcast_metadata["id"],
            "publish_date" : podcast_metadata["publish_time"],
            "subtitle_lang" : podcast_metadata["subtitle_lang"]
            # "youtube_object" : podcast_metadata['youtube_object']
        } ,
        "podcast_list" :[]
    }



def get_clips(state:AgentState):
    """
    Gets the best moments of the podcast using transcriptions.
    """
    print_yellow("GETTING BEST CLIPS ......")
    chain = moments_template | llm.with_structured_output(MomentsList)
    chunks = chunk_srt_by_chars(state["podcast"]["transcript"])
    moments:List[Moment] = []
    print("NUMBER OF CHUNKS :: " ,len(chunks))
    for chunk in chunks:
        result = chain.invoke({
            "podcast_title" : state["podcast"]["podcast_title"],
            "podcast_description" : state["podcast"]["podcast_description"],
            "transcript" : chunk["srt_text"]
        })
        for moment in result.Moments:
            moments.append(moment)
        time.sleep(5)

    return  {"Moments":moments }


def process_moments(state):
    """
    Extracts the subtitles of the moments from the main transcript.
    """
    clips = 0
    for i, moment in enumerate(state['Moments']):
        clips+=1
        
        subs = extract_srt_segment(state['podcast']['transcript'], moment.start_time, moment.end_time)
        save_srt(subs, f'./data/{i}_subs.srt')
    print_green(f"NO OF CLIPS :: {clips}")



def edit_video(state):
    """
    Edits the video trims, change orientation, adds the blur background effect , and burn the subtitles on the video
    """
    print_green("EDITING VIDEOS ......")
    process_moments(state)
    for i, moment in enumerate(state['Moments']):
        trim_media_input_data = {
    "input_file":"./data/current_podcast.mp4",
    "output_file":f"./data/{i}_index.mp4",
    "start_time":moment.start_time.replace(",", "."),
    "end_time":moment.end_time.replace(",", ".")
}

        trim_media(trim_media_input_data)

        convert_and_add_captions(f'./data/{i}_index.mp4' , f'./data/{i}_subs.srt' , f'./data/{i}_final.mp4')

def process_video(state):
    """
    Processes video extracts description metadata , subtitles
    """
    print_yellow("PROCESSING VIDEO .....")
    transcript = youtube_tool(state["podcast"]["video_id"] , state["podcast"]["subtitle_lang"])
    new_state = deepcopy(state)
    new_state["podcast"]["transcript"] = transcript
    return new_state

def post_video(state):
    """
    Posts the clips on youtube using v3 api
    """
    print_green("POSTING VIDEOS .....")
    post_metadata = []
    for i, moment in enumerate(state['Moments']):
        meta_data = {}
        meta_data['clip_addr'] = f'./data/{i}_final.mp4'
        meta_data['title'] = moment.title
        meta_data["description"] = moment.description
        meta_data["keywords"] = moment.keywords
        post_metadata.append(meta_data)
    #state['podcast']['video_id'] =  "EDBFFgs6Ifs"
    print("Final Metadata is :: " , post_metadata)
    with open('burnt_podcasts.json', 'r+') as fp:
        try:
            burnt_podcasts = json.load(fp)
        except json.JSONDecodeError:
            burnt_podcasts = []

        burnt_podcasts.append(state["podcast"]["video_id"])

        # Go back to beginning and truncate before dumping
        fp.seek(0)
        fp.truncate()
        json.dump(burnt_podcasts, fp, indent=2)
    print_yellow(f"UPLOADING {len(post_metadata)} videos ......")
    send_video.invoke(f"UPLOADING {len(post_metadata)} videos ...")
    for video in post_metadata:
        upload_video(video['clip_addr'] , metadata=video)
        time.sleep(300)

    folder_path = './data'

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)

    send_video.invoke("Completed cycle ...")
    return {
        "podcast" : {},
        "podcast_list" : [],
        "Moments":[],
        "agent_outcome": None,
        "intermediate_steps": []
    }


def where_to_go(state):
    """
    Changes the filter to current week/month if all the podcasts are burnt
    """
    if state['retry'] != None:
        send_video.invoke("Podcasts exhausted retrying with filter")
        return SEARCH_PODCASTS
    return PROCESS_VIDEO

def report_error_node(state):
    send_video.invoke("ERROR OCCURRED")
graph = StateGraph(AgentState)
graph.add_node(SEARCH_PODCASTS , search_podcasts)
graph.add_node(SELECT_BEST_PODCAST , get_best_podcast_from_llm)
graph.add_node(PROCESS_VIDEO , process_video)
graph.add_node(FETCH_CLIPS , get_clips)
graph.add_node(EDIT_VIDEO , edit_video)
graph.add_node(POST_VIDEO , post_video)
graph.add_node(REPORT_ERROR , report_error_node)

graph.add_conditional_edges(SELECT_BEST_PODCAST , where_to_go)
graph.add_edge(SEARCH_PODCASTS , SELECT_BEST_PODCAST)
graph.add_edge(SELECT_BEST_PODCAST , PROCESS_VIDEO)
graph.add_edge(PROCESS_VIDEO , FETCH_CLIPS)
graph.add_edge(FETCH_CLIPS , EDIT_VIDEO)
graph.add_edge(EDIT_VIDEO , POST_VIDEO)
graph.add_edge(POST_VIDEO , end_key=END)
graph.set_entry_point(SEARCH_PODCASTS)

app = graph.compile()

if __name__ == "__main__":
    app.invoke({
        "input": "Answer according to instructions.",
        "podcast": {},
        "Moments": [],
        "agent_outcome": None,
        "intermediate_steps": [],
        "podcast_list": [],
        "retry": None
    })
