import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

load_dotenv()

DB_URL = os.environ["DATABASE_URL"]
PDF_DIR = Path("../data/RAG_Data/_staging").resolve()

# Open-source embeddings (matches vector(1024))
EMBED_MODEL_NAME = "BAAI/bge-m3"

def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {PDF_DIR}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
    )

    embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            for pdf_path in pdfs:
                loader = PyPDFLoader(str(pdf_path))
                docs = loader.load()
                chunks = splitter.split_documents(docs)

                texts = [c.page_content for c in chunks]
                embeddings = embed_model.encode(texts, normalize_embeddings=True)

                doc_name = pdf_path.name
                for i, (text, emb) in enumerate(zip(texts, embeddings)):
                    cur.execute(
                        """
                        INSERT INTO policy_chunks (doc_name, section, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (doc_name, None, i, text, emb.tolist()),
                    )

            conn.commit()

    print(f"Ingested {len(pdfs)} PDFs into policy_chunks.")

if __name__ == "__main__":
    main()
