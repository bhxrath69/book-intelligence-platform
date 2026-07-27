import streamlit as st
import requests

API_BASE = "http://127.0.0.1:8000/api"

st.set_page_config(
    page_title="Book Intelligence Platform",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Book Intelligence Platform")
st.caption("RAG-powered book chat with Hybrid BM25 + Vector retrieval, MMR, and Redis caching")

with st.sidebar:
    st.header("📖 Select a Book")

    @st.cache_data(ttl=60)
    def fetch_books():
        try:
            r = requests.get(f"{API_BASE}/books/", timeout=10)
            if r.status_code != 200:
                return []
            data = r.json()
            if isinstance(data, list):
                return data
            return data.get("results", [])
        except Exception:
            return []

    books = fetch_books()

    if not books:
        st.error("Could not load books. Is Django running?")
        st.stop()

    book_options = {f"{b['title']} — {b['author']}": b['id'] for b in books}
    selected_label = st.selectbox("Choose a book", list(book_options.keys()))
    selected_book_id = book_options[selected_label]
    selected_book = next(b for b in books if b['id'] == selected_book_id)

    st.divider()
    st.subheader("📊 Stats")
    try:
        stats = requests.get(f"{API_BASE}/books/stats/", timeout=5).json()
        st.metric("Total Books", stats.get("total_books", 0))
        st.metric("Processed", stats.get("processed_books", 0))
        st.metric("Avg Rating", stats.get("average_rating", 0))
    except Exception:
        st.warning("Stats unavailable")

    st.divider()
    if st.button("🔄 New Conversation"):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()

col1, col2 = st.columns([1, 3])
with col1:
    if selected_book.get("cover_image_url"):
        st.image(selected_book["cover_image_url"], width=150)
    else:
        st.markdown("### 📕")

with col2:
    st.subheader(selected_book["title"])
    st.caption(f"by {selected_book['author']}")
    if selected_book.get("genre"):
        st.badge(selected_book["genre"])
    if selected_book.get("summary"):
        with st.expander("Summary"):
            st.write(selected_book["summary"])

st.divider()

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_book_id" not in st.session_state:
    st.session_state.last_book_id = None

if st.session_state.last_book_id != selected_book_id:
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.last_book_id = selected_book_id

st.subheader("💬 Chat with this book")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("cache_hit"):
            st.caption("⚡ Cache hit")
        if msg.get("retrieval"):
            st.caption(f"🔍 {msg['retrieval']}")

question = st.chat_input("Ask anything about this book...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                payload = {
                    "question": question,
                    "session_id": st.session_state.session_id
                }
                response = requests.post(
                    f"{API_BASE}/books/{selected_book_id}/chat/",
                    json=payload,
                    timeout=180
                )
                data = response.json()
                answer = data.get("answer", "No answer returned.")
                st.write(answer)

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if data.get("cache_hit"):
                        st.success("⚡ Cache hit")
                    else:
                        st.info("🧠 Fresh answer")
                with col_b:
                    if data.get("retrieval"):
                        st.caption(f"🔍 {data['retrieval']}")
                with col_c:
                    if data.get("sources"):
                        st.caption(f"📚 {', '.join(data['sources'])}")

                st.session_state.session_id = data.get("session_id")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "cache_hit": data.get("cache_hit", False),
                    "retrieval": data.get("retrieval", "")
                })

            except requests.exceptions.Timeout:
                st.error("Request timed out. Ollama is still processing — try again.")
            except Exception as e:
                st.error(f"Error: {e}")

with st.expander("📜 Full Session History"):
    try:
        history = requests.get(
            f"{API_BASE}/books/{selected_book_id}/history/",
            timeout=5
        ).json()
        if history:
            for session in history:
                st.markdown(f"**Session {session['session_id']}** — {session['created_at'][:10]}")
                for m in session["messages"]:
                    role_icon = "🧑" if m["role"] == "user" else "🤖"
                    st.markdown(f"{role_icon} **{m['role'].capitalize()}:** {m['content']}")
                st.divider()
        else:
            st.info("No history yet.")
    except Exception:
        st.warning("Could not load history.")
