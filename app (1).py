import json
import os
import random
import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="AI Quiz & Flashcard Generator",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 AI Quiz & Flashcard Generator")
st.caption("Turn your notes or any topic into practice quizzes and flashcards.")

# --- API configuration ---
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "OpenAI API key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="Your key is used only for requests made by this app.",
    )
    model = st.text_input("Model", value=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    st.divider()
    st.markdown("**How to use**")
    st.markdown(
        "1. Add a topic or paste your study notes.\n"
        "2. Choose Quiz or Flashcards.\n"
        "3. Generate and start studying."
    )

if "quiz" not in st.session_state:
    st.session_state.quiz = None
if "flashcards" not in st.session_state:
    st.session_state.flashcards = None
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False
if "flashcard_index" not in st.session_state:
    st.session_state.flashcard_index = 0
if "show_answer" not in st.session_state:
    st.session_state.show_answer = False


def get_client():
    if not api_key.strip():
        st.error("Add your OpenAI API key in the sidebar to generate study material.")
        st.stop()
    return OpenAI(api_key=api_key.strip())


def request_json(system_prompt: str, user_prompt: str):
    client = get_client()
    response = client.chat.completions.create(
        model=model.strip() or "gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("The AI returned an empty response.")
    return json.loads(content)


def make_quiz(source: str, count: int, difficulty: str):
    system = (
        "You are an expert educational assessment creator. Create accurate, clear "
        "questions based only on the supplied material when notes are provided. "
        "Return valid JSON with one key named 'questions'. Each question must have: "
        "'question' (string), 'options' (array of exactly four strings), "
        "'answer' (the exact correct option string), and 'explanation' (string). "
        "There must be exactly one correct option per question. Make distractors plausible."
    )
    user = (
        f"Create exactly {count} multiple-choice questions at {difficulty} difficulty.\n\n"
        f"Study material or topic:\n{source}\n\n"
        "Return JSON only."
    )
    data = request_json(system, user)
    questions = data.get("questions", [])
    if len(questions) != count:
        raise ValueError(f"Expected {count} questions, but received {len(questions)}.")
    for q in questions:
        if (
            not isinstance(q.get("question"), str)
            or not isinstance(q.get("options"), list)
            or len(q["options"]) != 4
            or q.get("answer") not in q["options"]
            or not isinstance(q.get("explanation"), str)
        ):
            raise ValueError("The AI returned a quiz with an invalid question format.")
    return questions


def make_flashcards(source: str, count: int):
    system = (
        "You are an expert study assistant. Create concise, useful flashcards. "
        "Return valid JSON with one key named 'flashcards'. Each card must contain "
        "'front' (a question, term, or prompt) and 'back' (a concise, accurate answer)."
    )
    user = (
        f"Create exactly {count} flashcards from this material or topic:\n\n"
        f"{source}\n\nReturn JSON only."
    )
    data = request_json(system, user)
    cards = data.get("flashcards", [])
    if len(cards) != count:
        raise ValueError(f"Expected {count} flashcards, but received {len(cards)}.")
    for card in cards:
        if not isinstance(card.get("front"), str) or not isinstance(card.get("back"), str):
            raise ValueError("The AI returned a flashcard with an invalid format.")
    return cards


# --- Main inputs ---
source = st.text_area(
    "Enter a topic or paste your study notes",
    height=190,
    placeholder="Example: Photosynthesis is the process by which green plants..."
)
left, right = st.columns(2)
with left:
    mode = st.radio("What would you like to create?", ["Quiz", "Flashcards"], horizontal=True)
with right:
    if mode == "Quiz":
        item_count = st.slider("Number of questions", 3, 20, 10)
    else:
        item_count = st.slider("Number of flashcards", 3, 30, 10)

difficulty = "Medium"
if mode == "Quiz":
    difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)

if st.button(f"✨ Generate {mode}", type="primary", use_container_width=True):
    if not source.strip():
        st.warning("Please enter a topic or paste some study notes first.")
    else:
        try:
            with st.spinner(f"Creating your {mode.lower()}..."):
                if mode == "Quiz":
                    st.session_state.quiz = make_quiz(source.strip(), item_count, difficulty)
                    st.session_state.quiz_submitted = False
                    st.session_state.flashcards = None
                else:
                    st.session_state.flashcards = make_flashcards(source.strip(), item_count)
                    st.session_state.flashcard_index = 0
                    st.session_state.show_answer = False
                    st.session_state.quiz = None
        except Exception as exc:
            st.error(f"Could not generate study material: {exc}")


# --- Quiz interface ---
if st.session_state.quiz:
    st.divider()
    st.subheader("📝 Your quiz")
    with st.form("quiz_form"):
        selected = {}
        for i, question in enumerate(st.session_state.quiz):
            st.markdown(f"**{i + 1}. {question['question']}**")
            selected[i] = st.radio(
                "Choose one answer:",
                question["options"],
                index=None,
                key=f"quiz_answer_{i}",
                label_visibility="collapsed",
            )
            st.markdown("")
        submitted = st.form_submit_button("Submit answers", type="primary")

    if submitted:
        st.session_state.quiz_submitted = True
        st.session_state.quiz_answers = selected

    if st.session_state.quiz_submitted:
        answers = st.session_state.get("quiz_answers", {})
        score = sum(
            1 for i, q in enumerate(st.session_state.quiz)
            if answers.get(i) == q["answer"]
        )
        total = len(st.session_state.quiz)
        st.metric("Your score", f"{score} / {total}", f"{(score / total) * 100:.0f}%")
        for i, q in enumerate(st.session_state.quiz):
            user_answer = answers.get(i)
            is_correct = user_answer == q["answer"]
            with st.expander(
                f"{'✅' if is_correct else '❌'} Question {i + 1}",
                expanded=not is_correct,
            ):
                st.write(q["question"])
                st.write(f"**Your answer:** {user_answer or 'Not answered'}")
                st.write(f"**Correct answer:** {q['answer']}")
                st.write(f"**Explanation:** {q['explanation']}")
        if st.button("Try this quiz again"):
            st.session_state.quiz_submitted = False
            st.rerun()


# --- Flashcard interface ---
if st.session_state.flashcards:
    st.divider()
    st.subheader("🗂️ Your flashcards")
    cards = st.session_state.flashcards
    index = st.session_state.flashcard_index
    card = cards[index]

    st.progress((index + 1) / len(cards), text=f"Card {index + 1} of {len(cards)}")
    with st.container(border=True):
        st.caption("QUESTION" if not st.session_state.show_answer else "ANSWER")
        if not st.session_state.show_answer:
            st.markdown(f"### {card['front']}")
        else:
            st.markdown(f"### {card['back']}")

    flip_label = "Hide answer" if st.session_state.show_answer else "Show answer"
    if st.button(f"👁️ {flip_label}", use_container_width=True):
        st.session_state.show_answer = not st.session_state.show_answer
        st.rerun()

    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("← Previous", disabled=index == 0, use_container_width=True):
            st.session_state.flashcard_index -= 1
            st.session_state.show_answer = False
            st.rerun()
    with next_col:
        if st.button("Next →", disabled=index == len(cards) - 1, use_container_width=True):
            st.session_state.flashcard_index += 1
            st.session_state.show_answer = False
            st.rerun()

    if st.button("🔀 Shuffle cards"):
        random.shuffle(st.session_state.flashcards)
        st.session_state.flashcard_index = 0
        st.session_state.show_answer = False
        st.rerun()

    with st.expander("View all flashcards"):
        for i, item in enumerate(cards, start=1):
            st.markdown(f"**{i}. {item['front']}**")
            st.write(item["back"])
            st.divider()

st.caption("Built with Streamlit and OpenAI. Review generated answers against your course material.")
