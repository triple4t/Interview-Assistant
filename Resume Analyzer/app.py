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

def analyze_resume(resume_text: str, job_description: str, required_skills: List[str]) -> dict:
    """Analyze the resume with a focus on experience and skills, ensuring a minimum score of 10%."""
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI HR assistant specialized in analyzing resumes. Focus primarily on the candidate's experience and skills, comparing them to the job requirements. Provide a detailed analysis and a percentage match, ensuring a minimum score of 10% for any resume."},
            {"role": "user", "content": f"""Analyze the following resume, focusing on the candidate's experience and skills. Compare them to the job description and required skills. Provide:
            1. A percentage match (a number between 10 and 100, with no decimal places)
            2. A summary of relevant experience (max 3 bullet points)
            3. A list of matching skills
            4. A list of missing skills
            5. Overall assessment (2-3 sentences)

            Remember, even if the resume doesn't seem to match well, give a minimum score of 10% to acknowledge the candidate's potential.

            Resume: {resume_text}

            Job Description: {job_description}

            Required Skills: {', '.join(required_skills)}"""}
        ],
        temperature=0.7
    )
    
    analysis = response.choices[0].message.content
    
    # Extract percentage match from the analysis
    try:
        percentage_match = int(analysis.split('\n')[0])
        if percentage_match < 10:
            percentage_match = 10
        elif percentage_match > 100:
            percentage_match = 100
    except:
        percentage_match = 10  # Default to 10% if parsing fails
    
    # Update the analysis text with the correct percentage
    analysis_lines = analysis.split('\n')
    analysis_lines[0] = str(percentage_match)
    updated_analysis = '\n'.join(analysis_lines)
    
    return {
        "percentage_match": percentage_match,
        "detailed_analysis": updated_analysis
    }

def main():
    st.set_page_config(page_title="Resume Analyzer App")
    st.title("Resume Analyzer App")

    # Job Description Input
    job_description = st.text_area("Enter Job Description", height=200)

    # Required Skills Input
    skills_input = st.text_input("Enter Required Skills (comma-separated)")
    required_skills = [skill.strip() for skill in skills_input.split(',') if skill.strip()]

    # Resume Upload
    uploaded_file = st.file_uploader(
        label="Upload Resume",
        type=list(DocumentLoader.supported_extensions.keys())
    )

    if not uploaded_file:
        st.info("Please upload a resume to continue.")
        return

    if st.button("Analyze Resume"):
        with st.spinner("Analyzing resume..."):
            # Save uploaded file temporarily
            temp_dir = tempfile.TemporaryDirectory()
            temp_filepath = os.path.join(temp_dir.name, uploaded_file.name)
            with open(temp_filepath, "wb") as f:
                f.write(uploaded_file.getvalue())

            # Load document
            docs = load_document(temp_filepath)
            resume_text = " ".join([doc.page_content for doc in docs])

            # Analyze resume
            analysis_result = analyze_resume(resume_text, job_description, required_skills)

            # Display results
            st.subheader("Analysis Results")
            st.progress(analysis_result["percentage_match"] / 100)
            st.write(f"Match Percentage: {analysis_result['percentage_match']}%")
            st.write("Detailed Analysis:")
            st.markdown(analysis_result["detailed_analysis"])

        st.success("Resume analysis completed!")

if __name__ == "__main__":
    main()
