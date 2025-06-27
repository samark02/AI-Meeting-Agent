import os
import json
import re
import html
import streamlit as st
import plotly.graph_objects as go
from google.cloud import storage
from google.oauth2 import service_account
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from scipy.ndimage import gaussian_filter1d
from datetime import timedelta, datetime
 
gcp_credentials = os.getenv('GCP_CREDENTIALS')
credentials_dict = json.loads(gcp_credentials)
creds = service_account.Credentials.from_service_account_info(credentials_dict)
client = storage.Client(credentials=creds)
bucket_name = "kapnotes"
bucket = client.bucket(bucket_name)
st.set_page_config(page_title="Kap Notes", layout="wide")

def get_client_names():
    blobs = list(bucket.list_blobs(prefix=""))
    client_names = set()
    for blob in blobs:
        client_name = blob.name.split("/")[0]
        client_names.add(client_name)
    return sorted(client_names)

def validate_data(client_name, date, meeting):
    summary_blob_name = f"{client_name}/{date}/{meeting}/summary.txt"
    transcription_blob_name = f"{client_name}/{date}/{meeting}/transcription.txt"
    audio_blob_name = f"{client_name}/{date}/{meeting}/audio.wav"
    summary_blob = bucket.blob(summary_blob_name)
    transcription_blob = bucket.blob(transcription_blob_name)
    audio_blob = bucket.blob(audio_blob_name)
    return summary_blob.exists() and transcription_blob.exists() and audio_blob.exists()

def get_meetings_for_date(client_name, date):
    prefix = f"{client_name}/{date}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    meetings = set()
    for blob in blobs:
        parts = blob.name.split("/")
        if len(parts) > 2 and parts[2]:
            meetings.add(parts[2])
    return sorted(meetings)

def get_dates_for_client(client_name):
    prefix = f"{client_name}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    dates = set()
    for blob in blobs:
        parts = blob.name.split("/")
        if len(parts) > 1 and parts[1]:
            dates.add(parts[1])
    return sorted(dates)

def login():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(125deg,rgb(253, 250, 220) 0%,rgb(214, 245, 255) 50%, #F8F8FF 100%);
            background-size: 200% 200%;
            animation: gradientMove 10s ease infinite;
        }
        @keyframes gradientMove {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        h1 {
            color: #4A4A4A;
            font-size: 3.5rem;
            font-weight: 900;
            text-align: center;
            margin-bottom: 3rem;
            letter-spacing: 2px;
        }
        .stButton > button {
            width: 100%;
            background: linear-gradient(45deg, #2563eb 0%, #3b82f6 100%);
            color: white;
            border: none;
            border-radius: 16px;
            padding: 1rem 1.5rem;
            font-size: 1.3rem;
            font-weight: bold;
            cursor: pointer;
            margin-top: 2rem;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4),
                        inset 0 -4px 8px rgba(0, 0, 0, 0.2),
                        inset 0 4px 8px rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            transform: translateY(-3px) scale(1.03);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.5),
                        inset 0 -4px 8px rgba(0, 0, 0, 0.2),
                        inset 0 4px 8px rgba(255, 255, 255, 0.2);
            background: linear-gradient(45deg, #1d4ed8 0%, #2563eb 100%);
        }
        </style>
    """, unsafe_allow_html=True)

    if 'password' not in st.session_state:
        st.session_state.password = ""
    
    st.markdown("<h1>KAP NOTES</h1>", unsafe_allow_html=True)
    
    client_names = get_client_names()
    client_name = st.selectbox("Select Client", client_names)
    
    if client_name:
        available_dates = get_dates_for_client(client_name)
        selected_date = st.selectbox(f"Available Dates for {client_name}", available_dates)
        
        if selected_date:
            available_meetings = get_meetings_for_date(client_name, selected_date)
            selected_meeting = st.selectbox(f"Available Meetings for {selected_date}", available_meetings)
            password = st.text_input("Enter Password", type="password", value=st.session_state.password)
            sign_in_button = st.button("Sign In", key="sign_in")
            if sign_in_button:
                if password == "kapnotes12345":
                    if validate_data(client_name, selected_date, selected_meeting):
                        st.session_state.client_name = client_name
                        st.session_state.date = selected_date
                        st.session_state.meeting = selected_meeting
                        st.session_state.logged_in = True
                        st.session_state.password = password
                        st.rerun()
                    else:
                        st.error(f"No records available for {client_name} on {selected_date}. Please select another option.")
                elif not password:
                    st.error("Please enter password.")
                else: 
                    st.error("Incorrect Password. Please try again.")
                    st.session_state.password = password
    

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
else:
    client_name = st.session_state.client_name
    date = st.session_state.date
    meeting = st.session_state.meeting
    password= st.session_state.password
 
    if st.sidebar.button("Back"):
        st.session_state.logged_in = False
        st.rerun() 

    st.sidebar.markdown(f'''
        <div class="client-name-container">
            <div class="client-name">{client_name}</div>
        </div>
    ''', unsafe_allow_html=True)

    css = '''
        <style>
        [data-testid="stExpander"] div:has(>.streamlit-expanderContent) {
            max-height: 400px;
            overflow-y: scroll;
        }
        [data-testid="stSidebar"] {
            min-width: 400px; 
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 10px;
        }
        .main {
            margin-top: 0 !important;
        }
        .summary-box, .keypoints-box, .action-items-box {
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.2), 0px 6px 15px rgba(0, 0, 0, 0.15);
            margin-top: 20px;
            margin-bottom: 30px;
            line-height: 1.8;
            font-size: 16px;
            color: #333;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .summary-box:hover, .keypoints-box:hover, .action-items-box:hover {
            transform: translateY(-0.1px) scale(1.05);
            box-shadow: 0px 12px 25px rgba(0, 0, 0, 0.25), 0px 18px 35px rgba(0, 0, 0, 0.2);
        }
        .summary-box {
            background: linear-gradient(145deg, #F1EAFF, #E5D4FF);
        }
        .keypoints-box {
            background: linear-gradient(145deg, #F1EAFF, #E5D4FF);
        }
        .action-items-box {
            background: linear-gradient(145deg, #F1EAFF, #E5D4FF);
        }
        .summary-box, .keypoints-box, .action-items-box {
            border: 1px solid rgba(0, 0, 0, 0.1);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2), 0 6px 18px rgba(0, 0, 0, 0.15);
        }
        .summary-box {
            background-color: #FFF8DC;
        }
        button:hover {
            background-color: white;
            color: black;
            border-color: black;
        }
        br {
            margin-top: 8px;
        }
        .audio-player-container {
            background: linear-gradient(135deg, #FF91A4, #FF4E00);
            padding: 25px;
            border-radius: 20px;
            box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.2), 0px 6px 25px rgba(0, 0, 0, 0.15);
            margin-top: 30px;
            margin-bottom: 40px;
            text-align: center;
            font-size: 18px;
            transition: all 0.7s ease-in-out, transform 0.3s ease;
        }
        .audio-player-container:hover {
            transform: translateY(-10px) scale(1.03);
            box-shadow: 0px 8px 25px rgba(0, 0, 0, 0.3), 0px 12px 35px rgba(0, 0, 0, 0.25);
        }
        .audio-player {
            width: 80%;
            height: 50px;
            border-radius: 15px;
            background-color: #FFF8DC;
            border: 1px solid rgba(0, 0, 0, 0.15);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2), 0 6px 18px rgba(0, 0, 0, 0.15);
            transition: all 0.3s ease, transform 0.3s ease;
        }
        .audio-player:hover {
            background-color: #FF7F50;
            transform: scale(1.1);
        }
        .audio-player-container h4 {
            color: #333;
            font-weight: 700;
            margin-bottom: 15px;
            font-size: 22px;
        }
        .audio-player-container .play-button {
            background-color: #FF4E00;
            border: none;
            padding: 10px 20px;
            color: white;
            font-weight: 600;
            border-radius: 30px;
            cursor: pointer;
            transition: all 0.5s ease;
        }
        .audio-player-container .play-button:hover {
            background-color: #FF91A4;
            box-shadow: 0px 4px 20px rgba(255, 145, 164, 0.5);
        }
        .audio-player-container .play-button:focus {
            outline: none;
        }
        .comment-box {
            background: linear-gradient(145deg, #f4f9fb, #dce5f5);
            border: 1px solid #cfd9e6;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 2px 2px 12px rgba(0, 0, 0, 0.1), -2px -2px 12px rgba(255, 255, 255, 0.8);
            font-family: 'Arial', sans-serif;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .comment-box:hover {
            transform: scale(1.02) translateY(-2px);
            box-shadow: 4px 4px 20px rgba(0, 0, 0, 0.2), -4px -4px 20px rgba(255, 255, 255, 0.4);
        }
        .comment-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-weight: bold;
            color: #3e3e3e;
        }
        .comment-text {
            color: #555;
            font-size: 14px;
            line-height: 1.6;
        }
        .comment-header span {
            color: #007bff;
            font-size: 12px;
        }
        .form-container {
            margin-bottom: 30px;
        }
        .stTextInput, .stTextArea {
            border-radius: 5px;
            border: 1px solid #ccc;
            padding: 10px;
            font-size: 14px;
            margin-bottom: 15px;
            width: 100%;
        }
        .stFormSubmitButton {
            color: black;
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 14px;
            cursor: pointer;
        }

        .client-name-container {
            padding: 20px;
            border-radius: 10px;
            background: linear-gradient(145deg, #ff7e5f, #feb47b);
            box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.1), -5px -5px 15px rgba(255, 255, 255, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .client-name-container:hover {
            transform: translateY(-5px) scale(1.05);
            box-shadow: 8px 8px 20px rgba(0, 0, 0, 0.15), -8px -8px 20px rgba(255, 255, 255, 0.4);
        }

        .client-name {
            font-size: 2.5rem;
            font-weight: 700;
            color: #fff;
            text-align: center;
            margin: 0;
        }

        .form-container {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .stButton>button {
            background-color: black;
            color: white;
            width: 150px;
            height: 40px;
            border: none;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
        }
        .stButton>button:hover {
            background-color: white;
            color: black;
        }
        </style>
    '''
    st.markdown(css, unsafe_allow_html=True)

    summary_blob_name = f"{client_name}/{date}/{meeting}/summary.txt"
    transcription_blob_name = f"{client_name}/{date}/{meeting}/transcription.txt" 
    audio_blob_name = f"{client_name}/{date}/{meeting}/audio.wav"

    bucket = client.bucket(bucket_name)

    summary_blob = bucket.blob(summary_blob_name)
    summary_content = summary_blob.download_as_text()

    audio_blob = bucket.blob(audio_blob_name)
    audio_url = audio_blob.generate_signed_url(expiration=timedelta(hours=1), method='GET')

    summary_match = re.search(r"Summary:\s*(.*?)(?=\nKey Points:)", summary_content, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else "Summary not found."

    key_points_match = re.search(r"Key Points:\s*(.*?)(?=\nAction Items:)", summary_content, re.DOTALL)
    key_points = re.findall(r"- (.*?)\n", key_points_match.group(1)) if key_points_match else ["Key points not found."]

    action_items_match = re.search(r"Action Items:\s*(.*)", summary_content, re.DOTALL)
    if action_items_match:
        action_items = re.findall(r"- (.*?)(?=\n- |$)", action_items_match.group(1), re.DOTALL)
    else:
        action_items = ["Action items not found."]

    transcription_blob = bucket.blob(transcription_blob_name)
    with transcription_blob.open("r") as file:
        meeting_data = json.load(file)

    speaker_data = {}
    total_talktime = 0

    for entry in meeting_data:
        speaker = entry["speaker"]
        duration = entry["end"] - entry["start"]
        text = entry["text"]
        total_talktime += duration

        if speaker not in speaker_data:
            speaker_data[speaker] = {"talktime": 0, "text": "", "words": 0}

        speaker_data[speaker]["talktime"] += duration
        speaker_data[speaker]["text"] += " " + text
        speaker_data[speaker]["words"] += len(text.split())

    for speaker, data in speaker_data.items():
        data["word_per_minute"] = round((data["words"] / data["talktime"] * 60), 2)
        data["talktime_percentage"] = round((data["talktime"] / total_talktime * 100), 2)

    combined_text = " ".join(data["text"] for data in speaker_data.values())

    analyzer = SentimentIntensityAnalyzer()
    sentences = combined_text.split('.')
    sentiment_polarity = [analyzer.polarity_scores(sentence)["compound"] for sentence in sentences if sentence.strip()]
    smoothed_polarity = gaussian_filter1d(sentiment_polarity, sigma=2)

    st.title("Kap Notes - Unveiling the story behind your meeting")

    st.markdown(f"### Summary\n<div class='summary-box'>{summary}</div>", unsafe_allow_html=True)

    st.markdown("### Meeting Highlights")
    st.markdown(
        f"<div class='keypoints-box'>" + "<br>".join(f"•&nbsp;{point}" for point in key_points) + "</div>",
        unsafe_allow_html=True
    )

    st.markdown("### Actionable Items")
    st.markdown(
        f"<div class='action-items-box'>" + "<br>".join(f"•&nbsp;{item}" for item in action_items) + "</div>",
        unsafe_allow_html=True
    )

    st.markdown("### Comments")

    if 'comments' not in st.session_state:
        st.session_state.comments = []

    def add_comment(comment):
        st.session_state.comments.append({"name": "", "comment": comment, "date": datetime.now().strftime("%d, %b %Y")})

    if 'name' not in st.session_state:
        st.session_state.name = ""
    if 'comment' not in st.session_state:
        st.session_state.comment = ""

    for comment in st.session_state.comments:
        st.markdown(
            f"""
            <div class="comment-box">
                <div class="comment-header">
                    <span>Admin</span>
                    <span>{comment['date']}</span>
                </div>
                <div class="comment-text">
                    {comment['comment']}
                </div>
            </div>
            """, unsafe_allow_html=True)

    with st.form(key="comment_form"):
        st.markdown('<div class="form-container">', unsafe_allow_html=True)
        comment_input = st.text_area("Your Comment", height=100, value=st.session_state.comment)
        submit_button = st.form_submit_button("Submit")
        st.markdown('</div>', unsafe_allow_html=True)

        if submit_button:
            if not comment_input:
                st.error("Enter your comment")  
            else:
                add_comment(comment_input)
                st.session_state.comment = "" 
                st.rerun()  

    with st.sidebar:

        speaker_names = list(speaker_data.keys())
        talk_time_percentages = [data["talktime_percentage"] for data in speaker_data.values()]

        color_palette = ["#A3BFF1", "#F4A7B9", "#C4F1D2", "#D6A7F2", "#FFD5A6", "#9BE1E6", "#F4A3C0", "#C1E7B4", "#F1D0FF", "#F9E9A6"]
        speaker_colors = {speaker: color_palette[i % len(color_palette)] for i, speaker in enumerate(speaker_names)} 

        st.markdown(f"""
        <div class="audio-player-container">
            <h4>Listen to the Meeting Audio</h4>
            <audio class="audio-player" controls>
                <source src="{audio_url}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
        """, unsafe_allow_html=True)
            
        st.title("Chat Conversation")
        
        with st.expander("Click to view the chat conversation", expanded=False):
            chat_conversation = ""
            for index, entry in enumerate(meeting_data):
                speaker = entry["speaker"]
                text = entry["text"]
                talk_time = entry["end"] - entry["start"]
                speaker_color = speaker_colors[speaker]
                chat_conversation += f"""
                <div style="margin-bottom: 20px; background-color: {speaker_color}; padding: 15px; 
                            border-radius: 10px; box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <b style="color: black;">{speaker}</b>
                        <span style="color: black;">{talk_time:.2f} mins</span>
                    </div>
                    <div style="margin-top: 10px; text-align: justify; line-height: 1.6; color: black;">
                        {text}
                    </div>
                </div>
                """
            st.markdown(chat_conversation, unsafe_allow_html=True)

        fig = go.Figure(data=[go.Pie(labels=speaker_names, values=talk_time_percentages, marker=dict(colors=list(speaker_colors.values())), hole=0.3)])
        fig.update_layout(
            title="Speaker Analytics",
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.2,
                xanchor="center",
                x=0.5
            )
        )
        st.plotly_chart(fig)

        st.markdown("### Sentiment Analysis of the Meeting")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(len(smoothed_polarity))), y=smoothed_polarity, mode='lines', name='Sentiment', line=dict(color='blue')))
        fig.update_layout(
            xaxis=dict(title="Time (in seconds)"),
            yaxis=dict(title="Sentiment Score", range=[-1, 1]),
        )
        st.plotly_chart(fig)
