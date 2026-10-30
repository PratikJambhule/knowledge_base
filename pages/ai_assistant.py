import streamlit as st
from pages.shared import handover_options
from services.common import query
from services.document_service import list_documents
from services.ai_service import generate_answer
from services.ai_service import AIServiceError
from services.vector_service import VectorIndexUnavailable, search_knowledge


def render(settings):
    st.title("AI Assistant")
    st.caption("Ask questions grounded in your stored project knowledge.")
    handovers = handover_options(settings)
    if not handovers:
        st.info("Create a knowledge transfer and add documents first.")
        return
    hmap = {f"{h['project_name']} · {h['title']}": h["id"] for h in handovers}
    selected = st.selectbox("Project or handover", list(hmap))
    question = st.text_area("Your question", placeholder="What are the remaining risks and who owns them?")
    if st.button("Ask KnowledgeBridge", type="primary") and question.strip():
        handover_id = hmap[selected]
        try:
            results = search_knowledge(settings.chroma_dir, question, handover_id)
            if results:
                context = "\n\n".join(
                    f"[{item['metadata'].get('filename', 'unknown document')}, "
                    f"section {item['metadata'].get('chunk_index', 'unknown')}]\n{item['text']}"
                    for item in results
                )
            else:
                context = "\n".join(d["extracted_text"] for d in list_documents(settings.database_path, handover_id))
            context += "\n" + "\n".join(
                f"[task] {r['title']} ({r['status']})"
                for r in query(settings.database_path, "SELECT title,status FROM tasks WHERE handover_id=?", (handover_id,))
            )
            st.write(generate_answer(settings.gemini_api_key, settings.gemini_model, question, context))
        except VectorIndexUnavailable:
            context = "\n".join(d["extracted_text"] for d in list_documents(settings.database_path, handover_id))
            st.info("Semantic index is unavailable; using stored SQLite document text.")
            try:
                st.write(generate_answer(settings.gemini_api_key, settings.gemini_model, question, context))
            except AIServiceError as exc:
                st.error(str(exc))
        except AIServiceError as exc:
            st.error(str(exc))
