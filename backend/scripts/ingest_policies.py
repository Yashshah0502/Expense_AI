# It takes PDF policy files → breaks them into small chunks → creates embeddings for each chunk → stores them in Postgres (policy_chunks) so /policy/search can retrieve them later.
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
        chunk_size=1024,
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

                texts_for_embedding = []
                final_chunks = []

                for i, c in enumerate(chunks):
                    page_num = c.metadata.get("page", 0) + 1
                    # Prepend metadata to content for better retrieval context
                    enriched_content = f"Document: {doc_name} | Page: {page_num}\n\n{c.page_content}"
                    texts_for_embedding.append(enriched_content)
                    final_chunks.append((i, enriched_content, page_num))

                if not texts_for_embedding:
                    continue
                    
                embeddings = get_embeddings(texts_for_embedding)

                for (idx, content, page), emb in zip(final_chunks, embeddings):
                    # We store "Page X" as the section title for now since we don't have real section headers
                    section_title = f"Page {page}"
                    cur.execute(
                        """
                        INSERT INTO policy_chunks (doc_name, section, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (doc_name, section_title, idx, content, emb),
                    )

            conn.commit()

    print(f"Ingested {len(pdfs)} PDFs into policy_chunks.")

if __name__ == "__main__":
    main()