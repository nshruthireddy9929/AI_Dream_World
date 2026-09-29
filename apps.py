import json
from google import genai
from google.genai import types
import streamlit as st

from twilio.rest import Client as TwilioClient

from prompts import SYSTEM_PROMPT, WELCOME_MESSAGE, SUMMARY_PROMPT


# ---------------- CONFIGURATION ----------------


GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TWILIO_ACCOUNT_SID=st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN=st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_CONTENT_SID=st.secrets["TWILIO_CONTENT_SID"]
TWILIO_WHATSAPP_FROM=st.secrets["TWILIO_WHATSAPP_FROM"]

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)

@st.cache_resource
def get_twilio_client():
    return TwilioClient(TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN)

twilio_client=get_twilio_client()
gemini_client = get_gemini_client()

# Use a model available in your Gemini API project
MODEL_NAME = "gemini-3.8-flash"

def clean_whatsapp_text(text):
    if not text:
        return "No Dream World summary available."
    text=" ".join(text.split())
    return text[:1500]+"..."if len(text)>1500 else text
    

def send_whatsapp(to_number,user_name,summary):
    try:
        content_variables=json.dumps(
            {"1": user_name,"2": clean_whatsapp_text(summary)},ensure_ascii=False
        )

        message = twilio_client.messages.create(
             from_=TWILIO_WHATSAPP_FROM,
               to=f"whatsapp:{to_number}", 
               content_sid=TWILIO_CONTENT_SID, 
               content_variables=content_variables,
        )
                
        return True, message.sid
    except Exception as error:
        return False, str(error)
    
    
def render_message(message):
    if message.get("kind") == "text":
        st.write(message.get("content", ""))

    elif message.get("kind") == "image":
        st.image(message.get("content"))

    else:
        st.write(message.get("content", ""))
    
def add_message(role, kind, content):
    st.session_state.messages.append({"role":role, "kind": kind,"content": content})
    render_message(st.session_state.messages[-1])

def ask_gemini(parts):
    try:
        return st.session_state.chat.send_message(parts).text
    except Exception as error:
        return f"Sorry, something went wrong: {error}"
# ---------------- SESSION STATE ----------------

if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------------- ONBOARDING ----------------

if not st.session_state.onboarded:

    st.title("🌌 AI DREAM WORLD")
    st.caption("Imagine. Explore. Create.")

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name",
            placeholder="Enter your name"
        )

        submitted = st.form_submit_button("Enter Dream World")

    if submitted:

        if not name.strip():
            st.warning("Please enter your name.")

        else:

            st.session_state.name = name.strip()

            # Create Gemini chat
            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
            )

            # Welcome message
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": WELCOME_MESSAGE
                }
            ]

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# ---------------- MAIN CHAT INTERFACE ----------------

# Header
header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center"
)

with header_col:
    st.title("🌌 AI DREAM WORLD")
    st.caption(f"Welcome, {st.session_state.name} ✨")

with button_col:
    if st.button("🗑️ New Chat"):

        st.session_state.messages = [
            {
                "role": "assistant",
                "content": WELCOME_MESSAGE
            }
        ]

        st.session_state.chat = gemini_client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            ),
        )

        st.rerun()


# ---------------- DISPLAY CHAT HISTORY ----------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.write(message["content"])


# ---------------- CHAT INPUT ----------------

user_input = st.chat_input(
    "✨ Ask anything and enter the Dream World..."
)


# ---------------- PROCESS USER MESSAGE ----------------

if user_input:

    # Save user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    # Display user message
    with st.chat_message("user"):
        st.write(user_input)

    # Send message to Gemini
    try:

        response = st.session_state.chat.send_message(
            user_input
        )

        assistant_response = response.text

    except Exception as e:

        assistant_response = (
            "Sorry, I couldn't process that request right now. "
            "Please try again."
        )

        st.error(f"Error: {e}")

    # Display AI response
    with st.chat_message("assistant"):
        st.write(assistant_response)

    # Save AI response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_response
        }
    )

header_col,button_col=st.columns([5,2],vertical_alignment="center")
with header_col:
    st.title("AI Dream World")

st.caption(f"Logged in as {st.session_state.name} ")
if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)

user_input=st.chat_input(
    "Ask a question, or attach a photo of your meal ",
    accept_file=True,
    file_type=["jpg","jpeg","png"],
)

if user_input:
    photo=user_input.files[0] if user_input.files else None
    text=user_input.text
    parts=[]

    if photo is not None:

        photo_bytes= photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))

    if text:

        add_message("user", "text", text)
        parts.append(text)

    elif photo is not None:

        parts.append("What is this meal? Give me the calories and macros.")

    with st.spinner("Crunching the numbers..."):
        answer = ask_gemini(parts)
    add_message("assistant", "text", answer)
