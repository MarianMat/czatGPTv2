import streamlit as st
from openai import OpenAI
import json
from pathlib import Path
from qdrant_utils import init_qdrant, save_to_qdrant

# 🔑 Inicjalizacja klienta OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
qdrant_client = init_qdrant()

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
        "default_personality": "Jesteś ekspertem AI, który pomaga tworzyć projekty w Pythonie z wykorzystaniem API OpenAI (GPT, Whisper, DALL·E itp.). Doradzasz w projektowaniu architektury, pisaniu kodu, integracjach oraz debugowaniu. Twoje odpowiedzi są rzeczowe, praktyczne i dostosowane do poziomu użytkownika. Pomagasz szybko i skutecznie budować aplikacje AI oparte na API."
    },
    "Українська": {
        "title": "🧠 МійGPT – Інтелектуальний чат з памʼяттю",
        "chat_title": "💬 Бесіда",
        "input_placeholder": "Задай запитання",
        "language_switch": "🌍 Мова інтерфейсу",
        "conversation_list": "📂 Виберіть бесіду",
        "new_conversation": "🔄 Нова бесіда",
        "default_conversation_name": "Бесіда {}",
        "model_select": "🤖 Виберіть модель GPT",
        "personality": "🎭 Стиль GPT",
        "memory_mode": "🧠 Режим памʼяті",
        "export_button": "📤 Експортувати бесіду",
        "download_txt": "⬇️ Завантажити як TXT",
        "cost_usd": "💰 Вартість (USD)",
        "cost_pln": "💰 Вартість (PLN)",
        "default_personality": "Ти є експертом з штучного інтелекту, який допомагає створювати проєкти на Python з використанням API OpenAI (GPT, Whisper, DALL·E тощо). Ти надаєш поради щодо архітектури, написання коду, інтеграцій та усунення помилок. Твої відповіді є лаконічними, практичними та адаптованими до рівня користувача. Ти допомагаєш швидко й ефективно створювати AI-додатки на основі OpenAI API."
    }
}

DB_PATH = Path("db")
DB_CONV_PATH = DB_PATH / "conversations"
DB_CONV_PATH.mkdir(parents=True, exist_ok=True)

def detect_topic(prompt: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Podaj krótki temat tej rozmowy w 3–5 słowach."},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content.strip()

def get_current_convo_id() -> int:
    f = DB_PATH / "current.json"
    if not f.exists():
        DB_PATH.mkdir(exist_ok=True)
        with open(f, "w") as fp:
            json.dump({"current_conversation_id": 1}, fp)
        return 1
    with open(f) as fp:
        return json.load(fp)["current_conversation_id"]

def list_conversations():
    files = DB_CONV_PATH.glob("*.json")
    convos = []
    for file in files:
        with open(file) as fp:
            c = json.load(fp)
            convos.append((c["id"], c["name"]))
    return sorted(convos, key=lambda x: x[0])

def create_new_conversation(name_template: str, default_personality: str):
    existing = list_conversations()
    new_id = max([cid for cid, _ in existing], default=0) + 1
    name = name_template.format(new_id)
    convo = {
        "id": new_id,
        "name": name,
        "chatbot_personality": default_personality,
        "messages": [],
        "model": "gpt-4o",
        "session_cost_usd": 0.0
    }
    with open(DB_CONV_PATH / f"{new_id}.json", "w") as fp:
        json.dump(convo, fp)
    with open(DB_PATH / "current.json", "w") as fp:
        json.dump({"current_conversation_id": new_id}, fp)
    st.session_state.clear()
    st.session_state.update(convo)

def delete_conversation(convo_id: int):
    convo_file = DB_CONV_PATH / f"{convo_id}.json"
    if convo_file.exists():
        convo_file.unlink()
        st.session_state.clear()

        new_convo = list_conversations()
        if new_convo:
            switch_conversation(new_convo[0][0])
        else:
            create_new_conversation("{0}", "Domyślna osobowość")
    else:
        st.warning("Konwersacja już nie istnieje.")

# Funkcja do zmiany rozmowy
def switch_conversation(convo_id: int):
    with open(DB_PATH / "current.json", "w") as fp:
        json.dump({"current_conversation_id": convo_id}, fp)
    with open(DB_CONV_PATH / f"{convo_id}.json") as fp:
        convo = json.load(fp)
        st.session_state.clear()
        st.session_state.update(convo)
    st.experimental_rerun()

def save_conversation():
    convo = {
        "id": st.session_state["id"],
        "name": st.session_state["name"],
        "chatbot_personality": st.session_state["chatbot_personality"],
        "messages": st.session_state.get("messages", []),
        "model": st.session_state["model"],
        "session_cost_usd": st.session_state.get("session_cost_usd", 0.0)
    }
    with open(DB_CONV_PATH / f"{convo['id']}.json", "w") as fp:
        json.dump(convo, fp)

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

lang = st.sidebar.selectbox(translations["Polski"]["language_switch"], ["Polski", "Українська"])
t = translations[lang]

# Załaduj lub stwórz konwersację
if "id" not in st.session_state:
    convo_id = get_current_convo_id()
    convo_file = DB_CONV_PATH / f"{convo_id}.json"
    if not convo_file.exists():
        create_new_conversation(t["default_conversation_name"], t["default_personality"])
    else:
        with open(convo_file) as fp:
            convo = json.load(fp)
        st.session_state.update(convo)

# Functions for searching in conversations
def search_conversations(query_word):
    matched_conversations = []
    conversations = list_conversations()
    for convo_id, _ in conversations:
        with open(DB_CONV_PATH / f"{convo_id}.json") as fp:
            convo = json.load(fp)
            for message in convo['messages']:
                if query_word.lower() in message['content'].lower():
                    matched_conversations.append((convo_id, message['content']))
    return matched_conversations

# sidebar: Nowa rozmowa
if st.sidebar.button(t["new_conversation"]):
    create_new_conversation(t["default_conversation_name"], t["default_personality"])

# sidebar: Lista rozmów z opcją usuwania
st.sidebar.markdown(f"**{t['conversation_list']}**")
for cid, name in list_conversations():
    cols = st.sidebar.columns([4, 1])
    if cols[0].button(f"{name}", key=f"load_{cid}"):
        switch_conversation(cid)
    if cols[1].button("🗑", key=f"delete_{cid}"):
        delete_conversation(cid)

# Search implementation
search_word = st.sidebar.text_input("Wyszukaj słowo kluczowe")
if st.sidebar.button("Szukaj"):
    results = search_conversations(search_word)
    if results:
        st.sidebar.markdown("**Wyniki wyszukiwania:**")
        for result in results:
            st.sidebar.write(f"ConvID: {result[0]} - {result[1][:50]}...")
    else:
        st.sidebar.write("Brak wyników.")

# sidebar: Zmiana nazwy konwersacji
new_name = st.sidebar.text_input("Zmień nazwę rozmowy", value=st.session_state["name"])
if st.sidebar.button("Zapisz nazwę"):
    st.session_state["name"] = new_name
    save_conversation()

# sidebar: Wybór modelu
st.sidebar.markdown("---")
st.sidebar.header("⚙️ " + t["model_select"])
st.session_state["model"] = st.sidebar.selectbox(
    t["model_select"],
    list(model_pricings.keys()),
    index=list(model_pricings.keys()).index(st.session_state["model"]),
    on_change=save_conversation
)
info = model_pricings[st.session_state["model"]]
st.sidebar.markdown(f"📌 *{info['Opis']}*")
st.sidebar.markdown(f"- Input: ${info['Input']} / 1M\n- Output: ${info['Output']} / 1M")

# sidebar: Tryb pamięci
st.sidebar.markdown("---")
st.sidebar.subheader(t["memory_mode"])
memory_mode_options = ["Ostatnie 10 wiadomości", "Rozszerzona (30)", "Pełna historia"]
st.session_state["memory_mode"] = st.sidebar.selectbox(
    t["memory_mode"],
    memory_mode_options,
    index=memory_mode_options.index(st.session_state.get("memory_mode", "Ostatnie 10 wiadomości"))
)

# sidebar: Styl GPT
st.sidebar.markdown("---")
st.sidebar.subheader(t["personality"])
st.session_state["chatbot_personality"] = st.sidebar.text_area(
    t["personality"],
    value=st.session_state["chatbot_personality"],
    height=150,
    on_change=save_conversation
)

# sidebar: Eksport
st.sidebar.markdown("---")
if st.sidebar.button(t["export_button"]):
    chat_txt = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.get("messages", [])])
    filename = f"{st.session_state['name'].replace(' ', '_')}.txt"
    st.sidebar.download_button(t["download_txt"], chat_txt, file_name=filename)

# sidebar: Koszt
usd_cost = st.session_state.get("session_cost_usd", 0.0)
total_cost_usd = 0.0
for cid, _ in list_conversations():
    with open(DB_CONV_PATH / f"{cid}.json") as fp:
        convo = json.load(fp)
        total_cost_usd += convo.get("session_cost_usd", 0.0)

st.sidebar.metric(t["cost_usd"], f"${usd_cost:.4f}")
st.sidebar.metric("Łączne koszty (USD)", f"${total_cost_usd:.4f}")
st.sidebar.metric(t["cost_pln"], f"{usd_cost * USD_TO_PLN:.4f}")
st.sidebar.metric("Łączne koszty (PLN)", f"{total_cost_usd * USD_TO_PLN:.4f}")

# 🧠 Główne okno czatu
st.title(t["title"])
st.subheader(f"{t['chat_title']}: {st.session_state['name']}")

# Wyświetlanie wiadomości
for msg in st.session_state.get("messages", []):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Obsługa nowego wprowadzenia użytkownika
prompt = st.chat_input(t["input_placeholder"])
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    if len(st.session_state.messages) == 1:
        topic = detect_topic(prompt)
        st.session_state.name = topic[:48]
    mem = st.session_state["memory_mode"]
    if mem == "Ostatnie 10 wiadomości":
        memory = st.session_state.messages[-10:]
    elif mem == "Rozszerzona (30)":
        memory = st.session_state.messages[-30:]
    else:
        memory = st.session_state.messages
    reply = get_reply(prompt, memory, st.session_state["model"], st.session_state["chatbot_personality"])
    st.session_state.messages.append(reply)
    st.session_state.session_cost_usd += (
        reply["usage"]["total_tokens"] * model_pricings[st.session_state["model"]]["Input"] / 1_000_000
        + reply["usage"]["completion_tokens"] * model_pricings[st.session_state["model"]]["Output"] / 1_000_000
    )
    with st.chat_message("assistant"):
        st.markdown(reply["content"])
    save_conversation()
    save_to_qdrant(prompt, reply["content"], f"Conv{st.session_state['id']}", qdrant_client)

