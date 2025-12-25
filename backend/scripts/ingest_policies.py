import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Add backend directory to sys.path to allow importing from rag
sys.path.append(str(Path(__file__).resolve().parent.parent))

from rag.embeddings import get_embeddings

load_dotenv()

DB_URL = os.environ["DATABASE_URL"]
PDF_DIR = Path("../data/RAG_Data/_staging").resolve()

def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {PDF_DIR}")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
    )

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            for pdf_path in pdfs:
                doc_name = pdf_path.name
                print(f"Processing {doc_name}...")
                
                # Idempotency: Delete existing chunks for this document
                cur.execute("DELETE FROM policy_chunks WHERE doc_name = %s", (doc_name,))
                
                loader = PyPDFLoader(str(pdf_path))
                docs = loader.load()
                chunks = splitter.split_documents(docs)

                texts = [c.page_content for c in chunks]
                if not texts:
                    continue
                    
                embeddings = get_embeddings(texts)

                for i, (text, emb) in enumerate(zip(texts, embeddings)):
                    cur.execute(
                        """
                        INSERT INTO policy_chunks (doc_name, section, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (doc_name, None, i, text, emb),
                    )

            conn.commit()

    print(f"Ingested {len(pdfs)} PDFs into policy_chunks.")

if __name__ == "__main__":
    main()
