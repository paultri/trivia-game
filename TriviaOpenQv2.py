import os
import time
import random
import requests
import html
from gtts import gTTS
import pygame
import speech_recognition as sr
from thefuzz import fuzz

# Initialize Pygame mixer
pygame.mixer.init()

# Define the 6 classic Trivial Pursuit categories and their corresponding OpenTDB API IDs
CATEGORY_MAP = {
    "Geography": [22],
    "Entertainment": [11, 14],  # Film or TV
    "History": [23],
    "Arts and Literature": [10], # Books
    "Science and Nature": [17],
    "Sports and Leisure": [21]
}

def speak(text):
    print(f"App says: {text}")
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        filename = "trivia_temp.mp3"
        tts.save(filename)
        
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
            
        pygame.mixer.music.unload()
        os.remove(filename)
    except Exception as e:
        print(f"Speech playback error: {e}")

# Initialize the Microphone
recognizer = sr.Recognizer()

def listen():
    with sr.Microphone() as source:
        print("\n[Listening... Speak your answer now]")
        recognizer.adjust_for_ambient_noise(source, duration=0.8)
        try:
            audio = recognizer.listen(source, timeout=9, phrase_time_limit=6)
            print("[Processing voice...]")
            text = recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text.lower()
        except sr.UnknownValueError:
            return "unknown_speech"
        except Exception as e:
            print(f"Microphone error: {e}")
            return None

def get_live_open_question(category_name):
    """Fetches a clean, direct question. Automatically rejects multiple-choice dependent phrasing."""
    api_ids = CATEGORY_MAP[category_name]
    chosen_id = random.choice(api_ids)
    
    # Loop until we find a question that doesn't rely on multiple-choice options
    while True:
        # Give it a 20% chance to pull a True/False question, 80% chance for a direct question
        question_type = "boolean" if random.random() < 0.2 else "multiple"
        
        url = f"https://opentdb.com/api.php?amount=1&category={chosen_id}&type={question_type}"
        try:
            response = requests.get(url).json()
            if response['response_code'] == 0:
                result = response['results'][0]
                question = html.unescape(result['question'])
                correct_answer = html.unescape(result['correct_answer']).strip().lower()
                
                # If it's True/False, append the prompt and it's ready to go
                if question_type == "boolean":
                    return question + " Is it true, or false?", correct_answer
                
                # If it's a multiple choice type, check for forbidden phrases
                forbidden_phrases = ["which of the following", "which of these", "all of the following", "except:"]
                question_lower = question.lower()
                
                if any(phrase in question_lower for phrase in forbidden_phrases):
                    print("[API Filter: Question relied on list choices. Fetching a replacement...]")
                    time.sleep(0.5) # Quick pause to obey API rate limits
                    continue 
                
                # If it passes the filter, it's a clean direct question!
                return question, correct_answer
                    
        except Exception as e:
            print(f"Error fetching data from database: {e}")
            time.sleep(1)
            
    return "What is the capital of New York state?", "albany"

def play_single_question(player_name, category_name):
    """Handles a single direct open-ended question."""
    full_question, correct_answer = get_live_open_question(category_name)
    
    speak(f"{player_name}, your category is: {category_name}.")
    speak(full_question)
    
    # Cheat sheet for the terminal viewer
    print(f"--- [DEBUG SECRET ANSWER: {correct_answer}] ---")
    
    user_answer = listen()
    
    if user_answer and user_answer != "unknown_speech":
        speak(f"I heard you say: {user_answer}.")
        
        match_score = fuzz.partial_ratio(correct_answer, user_answer)
        
        if match_score >= 80 or correct_answer in user_answer:
            speak("That is correct!")
            return True
        else:
            speak(f"Incorrect. The correct answer was {correct_answer}.")
            return False
    else:
        speak("I didn't catch an answer.")
        return False

def setup_game():
    print("--- DIRECT OPEN TRIVIAL PURSUIT SETUP ---")
    while True:
        try:
            num_players = int(input("Enter number of players: "))
            if num_players > 0:
                break
        except ValueError:
            print("Please enter a valid number.")
            
    game_state = {}
    for i in range(num_players):
        name = input(f"Enter name for Player {i+1}: ").strip()
        game_state[name] = {
            "completed_categories": set(),
            "eligible_for_win": False
        }
    return game_state

def game_loop():
    game_state = setup_game()
    players = list(game_state.keys())
    
    speak("Welcome to Trivial Pursuit! All score cards are clear. Let's begin.")
    
    current_player_index = 0
    game_is_running = True
    
    while game_is_running:
        current_player = players[current_player_index]
        player_data = game_state[current_player]
        completed = player_data["completed_categories"]
        
        speak(f"It is now {current_player}'s turn.")
        print(f"\n>>> Scoreboard Status for {current_player}: Points = {len(completed)}/6 | Categories remaining: {set(CATEGORY_MAP.keys()) - completed}")
        
        is_winning_turn = False
        
        if len(completed) < 6:
            remaining_categories = list(set(CATEGORY_MAP.keys()) - completed)
            chosen_category = random.choice(remaining_categories)
        else:
            is_winning_turn = True
            chosen_category = random.choice(list(CATEGORY_MAP.keys()))
            speak(f"Attention everyone! {current_player} is playing for the game winning seventh point!")
            time.sleep(0.5)

        # --- QUESTION 1 ---
        correct = play_single_question(current_player, chosen_category)
        time.sleep(1.0)
        
        if correct:
            if is_winning_turn:
                speak(f"Unbelievable! {current_player} answered correctly and has won the game! Congratulations!")
                print(f"\n🏆 {current_player} IS THE CHAMPION! 🏆")
                game_is_running = False
                break
            else:
                player_data["completed_categories"].add(chosen_category)
                
                if len(player_data["completed_categories"]) == 6:
                    speak(f"Incredible! That was your sixth category! Your turn is now over. Next round you go for the win.")
                    correct = False 
                else:
                    speak(f"You have unlocked that category! You earn one bonus question.")
                    
                    remaining_categories = list(set(CATEGORY_MAP.keys()) - player_data["completed_categories"])
                    chosen_category_2 = random.choice(remaining_categories)
                    
                    # Run Question 2
                    correct_2 = play_single_question(current_player, chosen_category_2)
                    if correct_2:
                        player_data["completed_categories"].add(chosen_category_2)
                        if len(player_data["completed_categories"]) == 6:
                            speak(f"That is six categories total! You are locked in for the win next round.")
                    time.sleep(1.0)
                    
        speak(f"That concludes {current_player}'s turn.")
        print("----------------------------------------------------------------------")
        
        current_player_index = (current_player_index + 1) % len(players)
        
        if game_is_running:
            choice = input("Press Enter to continue to next player, or type 'exit' to quit: ").strip().lower()
            if choice == 'exit':
                game_is_running = False
                speak("Game cancelled. Thanks for playing!")

if __name__ == "__main__":
    game_loop()