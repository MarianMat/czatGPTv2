import streamlit as st
from openai import OpenAI
from qdrant_utils import init_qdrant, save_to_qdrant
from db_utils import init_db, create_conversation, list_conversations, get_messages, save_message, get_conversation
import json
from datetime import datetime

# --- Inicjalizacja ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
qdrant_client = init_qdrant()
init_db()  # upewnij się, że baza SQLite jest gotowa

model_pricings = {
    "gpt-4o": {"Opis": "Multimodalny – tekst, obraz, głos", "Input": 2.5, "Output": 10.0},
    "gpt-4o-mini": {"Opis": "Lekki i tani do chatbotów", "Input": 0.15, "Output": 0.6},
    "gpt-4-turbo": {"Opis": "Szybki tekstowy model", "Input": 1.5, "Output": 6.0},
    "gpt-3.5-turbo": {"Opis": "Budżetowa opcja", "Input": 0.5, "Output": 1.5}
}
USD_TO_PLN = 3.97

translations = {
    "Polski": {
        "title": "🧠 MójGPT – Inteligentny czat z pamięcią",
        "chat_title": "💬 Rozmowa",
        "input_placeholder": "Zadaj pytanie",
        "language_switch": "🌍 Język interfejsu",
        "conversation_list": "📂 Wybierz rozmowę",
        "new_conversation": "🔄 Nowa rozmowa",
        "default_conversation_name": "Rozmowa {}",
        "model_select": "🤖 Wybierz model GPT",
        "personality": "🎭 Styl GPT",
        "memory_mode": "🧠 Tryb pamięci",
        "export_button": "📤 Eksportuj rozmowę",
        "download_txt": "⬇️ Pobierz jako TXT",
        "cost_usd": "💰 Koszt (USD)",
        "cost_pln": "💰 Koszt (PLN)",
        "default_personality": "Jesteś ekspertem AI, który pomaga tworzyć projekty w Pythonie z wykorzystaniem API OpenAI."
    }
}

def get_reply(prompt: str, memory: list, model: str, personality: str) -> dict:
    msgs = [{"role": "system", "content": personality}] + memory + [{"role": "user", "content": prompt}]
    resp = client.chat.completions.create(model=model, messages=msgs)
    usage = resp.usage
    return {
        "role": "assistant",
        "content": resp.choices[0].message.content,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }
    }

st.set_page_config(page_title="MójGPT", layout="centered")

# --- Stan aplikacji ---
if "conversation_id" not in st.session_state:
    # Jeśli brak aktywnej rozmowy → stwórz nową
    convo_id = create_conversation(
        "Nowa rozmowa",
        translations["Polski"]["default_personality"],
        "gpt-4o",
        "Pełna historia",
        "Polski"
    )
    st.session_state.conversation_id = convo_id
    st.session_state.model = "gpt-4o"
    st.session_state.chatbot_personality = translations["Polski"]["default_personality"]
    st.session_state.memory_mode = "Pełna historia"

# --- Wybór języka ---
lang = st.sidebar.selectbox(
    translations["Polski"]["language_switch"],
    ["Polski"],
    index=0
)
t = translations[lang]

# --- Sidebar: Nowa rozmowa ---
if st.sidebar.button(t["new_conversation"]):
    convo_id = create_conversation(
        t["default_conversation_name"].format(datetime.now().strftime("%H:%M")),
        t["default_personality"],
        "gpt-4o",
        "Pełna historia",
        lang
    )
    st.session_state.conversation_id = convo_id

# --- Sidebar: Lista rozmów ---
st.sidebar.markdown(f"**{t['conversation_list']}**")
for cid, name in list_conversations():
    if st.sidebar.button(name, key=f"conv_{cid}"):
        st.session_state.conversation_id = cid

# --- Sidebar: Model ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ " + t["model_select"])
st.session_state.model = st.sidebar.selectbox(
    t["model_select"],
    list(model_pricings.keys()),
    index=list(model_pricings.keys()).index(st.session_state.get("model", "gpt-4o"))
)

# --- Sidebar: Tryb pamięci ---
st.sidebar.markdown("---")
memory_mode_options = ["Ostatnie 10 wiadomości", "Rozszerzona (30)", "Pełna historia"]
st.session_state.memory_mode = st.sidebar.selectbox(
    t["memory_mode"],
    memory_mode_options,
    index=memory_mode_options.index(st.session_state.get("memory_mode", "Pełna historia"))
)

# --- Sidebar: Styl GPT ---
st.sidebar.markdown("---")
st.sidebar.subheader(t["personality"])
st.session_state.chatbot_personality = st.sidebar.text_area(
    t["personality"],
    value=st.session_state.get("chatbot_personality", translations["Polski"]["default_personality"]),
    height=150
)

# --- Główne okno ---
st.title(t["title"])
conv = get_conversation(st.session_state.conversation_id)
st.subheader(f"{t['chat_title']}: {conv[1]}")  # nazwa rozmowy

# --- Historia czatu ---
messages = get_messages(st.session_state.conversation_id)
for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Obsługa inputu ---
prompt = st.chat_input(t["input_placeholder"])
if prompt:
    save_message(st.session_state.conversation_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    # Dobór pamięci
    if st.session_state.memory_mode == "Ostatnie 10 wiadomości":
        memory = messages[-10:]
    elif st.session_state.memory_mode == "Rozszerzona (30)":
        memory = messages[-30:]
    else:
        memory = messages

    # Generowanie odpowiedzi
    reply = get_reply(prompt, memory, st.session_state.model, st.session_state.chatbot_personality)
    save_message(st.session_state.conversation_id, "assistant", reply["content"])
    with st.chat_message("assistant"):
        st.markdown(reply["content"])

    # Zapis do Qdrant
    save_to_qdrant(prompt, reply["content"], f"Conv{st.session_state['conversation_id']}", qdrant_client)
