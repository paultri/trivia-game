import streamlit as st
import random
import requests
import html
from thefuzz import fuzz
from gtts import gTTS
import base64
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Trivial Pursuit", page_icon="🏆", layout="centered")

st.markdown("""
    <style>
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# Define categories and their API IDs
CATEGORY_MAP = {
    "Geography": [22],
    "Entertainment": [11, 14],
    "History": [23],
    "Arts and Literature": [10],
    "Science and Nature": [17],
    "Sports and Leisure": [21]
}

# --- AUDIO PLAYER HELPER ---
def autoplay_audio(text):
    """Generates speech via gTTS and embeds it dynamically using an isolated audio container."""
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        b64 = base64.b64encode(mp3_fp.read()).decode()
        
        # Isolated HTML5 audio block that auto-plays cleanly
        md = f"""
            <iframe src="data:audio/mp3;base64,{b64}" allow="autoplay" style="display:none" id="audio_iframe"></iframe>
            <audio autoplay style="display:none;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Audio Error: {e}")

# --- API TRIVIA FETCH ---
def fetch_filtered_question(category_name):
    """Fetches a question and filters out multiple-choice specific wording."""
    api_ids = CATEGORY_MAP[category_name]
    chosen_id = random.choice(api_ids)
    
    while True:
        question_type = "boolean" if random.random() < 0.2 else "multiple"
        url = f"https://opentdb.com/api.php?amount=1&category={chosen_id}&type={question_type}"
        try:
            response = requests.get(url).json()
            if response['response_code'] == 0:
                result = response['results'][0]
                question = html.unescape(result['question'])
                correct_answer = html.unescape(result['correct_answer']).strip().lower()
                
                if question_type == "boolean":
                    return question + " Is it true, or false?", correct_answer
                
                forbidden = ["which of the following", "which of these", "all of the following", "except:"]
                if any(phrase in question.lower() for phrase in forbidden):
                    continue
                    
                return question, correct_answer
        except:
            return "What is the capital of New York state?", "albany"

# --- IMPORT MIC RECORDER SAFELY ---
try:
    from streamlit_mic_recorder import speech_to_text
except ImportError:
    st.error("Please ensure 'streamlit-mic-recorder' is in your requirements.txt file.")

# --- SESSION STATE INITIALIZATION ---
if "game_started" not in st.session_state:
    st.session_state.game_started = False
    st.session_state.players = []
    st.session_state.game_state = {}
    st.session_state.current_idx = 0
    st.session_state.turn_phase = "start"
    st.session_state.current_question = ""
    st.session_state.current_answer = ""
    st.session_state.chosen_category = ""
    st.session_state.is_winning_turn = False
    st.session_state.questions_asked_this_turn = 0
    st.session_state.audio_to_play = ""
    st.session_state.user_said = ""
    st.session_state.was_correct = False

# --- SCREEN 1: GAME SETUP ---
if not st.session_state.game_started:
    st.title("🏆 Hybrid Trivial Pursuit Setup")
    st.write("Set up your game night below:")
    
    num_players = st.number_input("Number of Players", min_value=1, max_value=8, value=2, step=1)
    
    player_names = []
    for i in range(int(num_players)):
        name = st.text_input(f"Player {i+1} Name", value=f"Player {i+1}", key=f"pname_{i}")
        player_names.append(name.strip())
        
    if st.button("Start Game", use_container_width=True):
        st.session_state.players = player_names
        st.session_state.game_state = {
            name: {"completed_categories": set()} for name in player_names
        }
        st.session_state.game_started = True
        st.session_state.turn_phase = "start"
        st.rerun()

# --- SCREEN 2: ACTIVE GAME PLAY ---
else:
    st.title("🎲 Trivial Pursuit Party")
    
    # Run audio if there is any queued up for this specific page render
    if st.session_state.audio_to_play:
        autoplay_audio(st.session_state.audio_to_play)
        st.session_state.audio_to_play = "" 
    
    players = st.session_state.players
    current_player = players[st.session_state.current_idx]
    player_data = st.session_state.game_state[current_player]
    completed = player_data["completed_categories"]
    
    # --- VISUAL SCOREBOARD SIDEBAR ---
    st.sidebar.title("Leaderboard")
    for p in players:
        pts = len(st.session_state.game_state[p]["completed_categories"])
        st.sidebar.markdown(f"### **{p}**: {pts}/6 categories")
        cats_str = ""
        for cat in CATEGORY_MAP.keys():
            if cat in st.session_state.game_state[p]["completed_categories"]:
                cats_str += "🟩 "
            else:
                cats_str += "⬜ "
        st.sidebar.caption(cats_str)
    
    st.divider()
    
    # --- PHASE 1: START OF TURN ---
    if st.session_state.turn_phase == "start":
        st.subheader(f"It is **{current_player}**'s Turn!")
        
        if len(completed) == 6:
            st.session_state.is_winning_turn = True
            st.session_state.chosen_category = random.choice(list(CATEGORY_MAP.keys()))
            announcement = f"Attention everyone! This question is for the game winning seventh point!"
        else:
            st.session_state.is_winning_turn = False
            remaining = list(set(CATEGORY_MAP.keys()) - completed)
            st.session_state.chosen_category = random.choice(remaining)
            announcement = ""
            
        st.info(f"Category drawn: **{st.session_state.chosen_category}**")
        if announcement:
            st.warning(announcement)
        
        if st.button("🎙️ Load & Hear Question", use_container_width=True):
            q, a = fetch_filtered_question(st.session_state.chosen_category)
            st.session_state.current_question = q
            st.session_state.current_answer = a
            st.session_state.turn_phase = "listening"
            st.session_state.questions_asked_this_turn += 1
            
            if st.session_state.is_winning_turn:
                st.session_state.audio_to_play = f"{current_player}, this is for the win. Your category is {st.session_state.chosen_category}. Here is the question: {q}"
            else:
                st.session_state.audio_to_play = f"{current_player}, your category is {st.session_state.chosen_category}. Here is the question: {q}"
            st.rerun()

    # --- PHASE 2: LISTENING FOR SPOKEN ANSWER ---
    elif st.session_state.turn_phase == "listening":
        st.markdown(f"### Category: *{st.session_state.chosen_category}*")
        st.warning(f"**Question for {current_player}:** {st.session_state.current_question}")
        
        # Action Bar: Repeat Question Side-by-Side with the host expander
        col1, col2 = st.columns([1, 1])
        with col1:
            # We explicitly target the audio queue and reset the mic instance key so it triggers fresh audio
            if st.button("🔊 Repeat Question", use_container_width=True):
                st.session_state.audio_to_play = f"The question is: {st.session_state.current_question}"
                st.rerun()
        with col2:
            with st.expander("Show Secret Answer"):
                st.write(f"Expected Answer: **{st.session_state.current_answer}**")
            
        st.write("Tap the microphone button, say your answer clearly, and stop recording:")
        
        spoken_text = speech_to_text(start_prompt="🔴 TAP TO RECORD ANSWER", stop_prompt="⏹️ STOP", language='en', key=f'speech_{st.session_state.questions_asked_this_turn}')
        
        if spoken_text:
            user_ans = spoken_text.strip().lower()
            correct_ans = st.session_state.current_answer
            
            match_score = fuzz.partial_ratio(correct_ans, user_ans)
            is_correct = match_score >= 80 or correct_ans in user_ans
            
            st.session_state.user_said = spoken_text
            st.session_state.was_correct = is_correct
            
            if is_correct:
                if st.session_state.is_winning_turn:
                    st.session_state.turn_phase = "game_over"
                else:
                    st.session_state.game_state[current_player]["completed_categories"].add(st.session_state.chosen_category)
                    
                    if len(st.session_state.game_state[current_player]["completed_categories"]) == 6:
                        st.session_state.turn_phase = "resolved"
                        st.session_state.audio_to_play = f"That is correct! You have unlocked your final category. Your turn is complete."
                    elif st.session_state.questions_asked_this_turn < 2:
                        st.session_state.turn_phase = "bonus_ready"
                    else:
                        st.session_state.turn_phase = "resolved"
                        st.session_state.audio_to_play = f"That is correct! Category unlocked."
            else:
                st.session_state.turn_phase = "resolved"
                st.session_state.audio_to_play = f"Incorrect. You said {user_ans}. The correct answer was {correct_ans}."
            st.rerun()

    # --- PHASE 2.5: BONUS READY TRAFFIC CONTROL ---
    elif st.session_state.turn_phase == "bonus_ready":
        st.success(f"Correct! You said '{st.session_state.user_said}'. Category unlocked!")
        
        if st.button("Bring on the Bonus Question! ➡️", use_container_width=True):
            remaining = list(set(CATEGORY_MAP.keys()) - st.session_state.game_state[current_player]["completed_categories"])
            st.session_state.chosen_category = random.choice(remaining)
            
            q, a = fetch_filtered_question(st.session_state.chosen_category)
            st.session_state.current_question = q
            st.session_state.current_answer = a
            st.session_state.turn_phase = "listening"
            st.session_state.questions_asked_this_turn += 1
            
            st.session_state.audio_to_play = f"That is correct! You earned a bonus question. Your new category is {st.session_state.chosen_category}. {q}"
            st.rerun()

    # --- PHASE 3: TURN CONCLUDED ---
    elif st.session_state.turn_phase == "resolved":
        if st.session_state.was_correct:
            st.success(f"Correct! You said '{st.session_state.user_said}'.")
            if len(st.session_state.game_state[current_player]["completed_categories"]) == 6:
                st.balloons()
                st.info("6 categories reached! Turn ends automatically. Next round you go for the win.")
        else:
            st.error(f"Incorrect. You said '{st.session_state.user_said}'. The correct answer was: {st.session_state.current_answer}")
            
        if st.button("Pass Phone to Next Player ➡️", use_container_width=True):
            st.session_state.questions_asked_this_turn = 0
            st.session_state.current_idx = (st.session_state.current_idx + 1) % len(players)
            st.session_state.turn_phase = "start"
            st.rerun()
            
    # --- PHASE 4: CHAMPION HIGHLIGHT ---
    elif st.session_state.turn_phase == "game_over":
        st.balloons()
        st.title(f"🏆 {current_player} WINS THE GAME! 🏆")
        st.success(f"Incredible! The winning answer was '{st.session_state.current_answer}' and you completely nailed it.")
        
        st.session_state.audio_to_play = f"Congratulations to {current_player}, you are the trivial pursuit grand champion!"
        
        if st.button("Play Again 🔄", use_container_width=True):
            st.session_state.game_started = False
            st.rerun()
