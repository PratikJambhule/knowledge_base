import streamlit as st
from pages.shared import handover_options
from services.document_service import save_document, list_documents, search_documents


def render(settings):
    st.title("Knowledge Base")
    handovers = handover_options(settings)
    hmap = {"Global knowledge": None} | {f"{h['project_name']} · {h['title']}": h["id"] for h in handovers}
    with st.form("upload"):
        selected = st.selectbox("Link to", list(hmap))
        files = st.file_uploader("Upload PDF, DOCX or TXT", type=["pdf", "docx", "txt"], accept_multiple_files=True)
        if st.form_submit_button("Index documents"):
            for file in files or []:
                try:
                    save_document(settings.database_path, settings.upload_dir, hmap[selected], file.name, file.getvalue(), settings.chroma_dir)
                    st.success(f"Indexed {file.name}")
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
    search = st.text_input("Search knowledge")
    documents = search_documents(settings.database_path, search) if search else list_documents(settings.database_path)
    for doc in documents:
        with st.expander(f"📄 {doc['title']} · {doc['file_type']}"):
            st.caption(doc["file_name"])
            st.write(doc["extracted_text"][:2000])
