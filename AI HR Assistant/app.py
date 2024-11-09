import streamlit as st
import openai
import os
import tempfile
from typing import Any, List
from langchain.document_loaders import (
    PyPDFLoader, TextLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredEPubLoader
)
import logging
import pathlib
from langchain.schema import Document
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import DocArrayInMemorySearch
from langchain.schema import BaseRetriever
from dotenv import load_dotenv, find_dotenv

# Load environment variables
_ = load_dotenv(find_dotenv())
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

class EpubReader(UnstructuredEPubLoader):
    def __init__(self, file_path: str | list[str], **kwargs: Any):
        super().__init__(file_path, **kwargs, mode="elements", strategy="fast")

class DocumentLoaderException(Exception):
    pass

class DocumentLoader:
    """Loads in a document with a supported extension."""
    supported_extensions = {
        ".pdf": PyPDFLoader,
        ".txt": TextLoader,
        ".epub": EpubReader,
        ".docx": UnstructuredWordDocumentLoader,
        ".doc": UnstructuredWordDocumentLoader
    }

def load_document(temp_filepath: str) -> List[Document]:
    """Load a file and return it as a list of documents."""
    ext = pathlib.Path(temp_filepath).suffix
    loader = DocumentLoader.supported_extensions.get(ext)
    if not loader:
        raise DocumentLoaderException(
            f"Invalid extension type {ext}, cannot load this type of file"
        )
    loader = loader(temp_filepath)
    docs = loader.load()
    logging.info(docs)
    return docs

def configure_retriever(docs: List[Document]) -> BaseRetriever:
    """Retriever to use."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectordb = DocArrayInMemorySearch.from_documents(splits, embeddings)
    return vectordb.as_retriever(search_type="mmr", search_kwargs={"k": 2, "fetch_k": 4})

def generate_relevant_questions(resume_text: str) -> List[str]:
    """Generate relevant HR interview questions based on the resume."""
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI HR assistant. Generate 5 relevant interview questions based on the provided resume."},
            {"role": "user", "content": resume_text}
        ],
        temperature=0.7
    )
    questions = response.choices[0].message.content.split("\n")
    return [q.strip() for q in questions if q.strip()]

def text_to_audio(input_text, audio_path):
    """Convert text to audio."""
    response = openai.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=input_text
    )
    response.stream_to_file(audio_path)

def main():
    st.set_page_config(page_title="AI HR Assistant: Interview Questions Generator")
    st.title("AI HR Assistant: Generate Interview Questions from Resumes")

    uploaded_file = st.file_uploader(
        label="Upload Resume",
        type=list(DocumentLoader.supported_extensions.keys())
    )

    if not uploaded_file:
        st.info("Please upload a resume to continue.")
        return

    if st.button("Generate Questions"):
        with st.spinner("Processing resume and generating questions..."):
            # Save uploaded file temporarily
            temp_dir = tempfile.TemporaryDirectory()
            temp_filepath = os.path.join(temp_dir.name, uploaded_file.name)
            with open(temp_filepath, "wb") as f:
                f.write(uploaded_file.getvalue())

            # Load document
            docs = load_document(temp_filepath)
            resume_text = " ".join([doc.page_content for doc in docs])

            # Generate questions
            questions = generate_relevant_questions(resume_text)

            # Display questions and generate audio
            st.subheader("Generated Interview Questions:")
            for i, question in enumerate(questions, 1):
                st.write(f"{i}. {question}")

                # Generate audio for the question
                audio_file_path = f"question_{i}.mp3"
                text_to_audio(question, audio_file_path)

                # Display audio player
                st.audio(audio_file_path)

        st.success("Questions generated successfully!")

if __name__ == "__main__":
    main()