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

import hashlib
import json

def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

import re
from langchain_core.documents import Document

def infer_org(doc_name: str) -> str:
    # "ASU_Travel.pdf" -> "ASU"
    # "ASU.pdf" -> "ASU" via split("_") fallback logic or just string manip
    # Robust: split by first underscore if present, else first dot
    name = doc_name.rsplit('.', 1)[0]
    if "_" in name:
        return name.split("_")[0].upper()
    return name.upper() 

def infer_policy_type(doc_name: str, text: str) -> str:
    name = doc_name.lower()
    t = text.lower()
    if "travel" in name or "travel" in t:
        return "travel"
    if "procure" in name or "p-card" in t or "p card" in t:
        return "procurement"
    return "general"

def infer_section_title(chunk_text: str) -> str | None:
    for line in chunk_text.splitlines()[:12]:
        s = line.strip()
        # Heuristic: Uppercase or Numbered (1.2, 5, etc)
        if 5 <= len(s) <= 80 and (s.isupper() or re.match(r"^\d+(\.\d+)*\s+\w+", s)):
            return s
    return None

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
                
                # 1. Load existing hashes for this doc
                cur.execute(
                    "SELECT chunk_index, content_hash FROM policy_chunks WHERE doc_name = %s",
                    (doc_name,),
                )
                existing_hashes = {idx: h for idx, h in cur.fetchall()}
                
                loader = PyPDFLoader(str(pdf_path))
                raw_docs = loader.load()
                
                # Convert to page-aware Documents if needed, but PyPDFLoader already does this.
                # raw_docs[i].metadata["page"] is 0-indexed page number.
                # We can just use split_documents directly as it generally preserves metadata.
                
                chunks = splitter.split_documents(raw_docs)

                current_chunk_indexes = []
                rows_to_upsert = []
                
                texts_to_embed = []
                
                for i, c in enumerate(chunks):
                    current_chunk_indexes.append(i)
                    page_num = c.metadata.get("page", 0) + 1
                    
                    # Metadata Extraction
                    org = infer_org(doc_name)
                    policy_type = infer_policy_type(doc_name, c.page_content)
                    title_candidate = infer_section_title(c.page_content)
                    # Fallback to "Page X" if no specific title found
                    section_title = title_candidate if title_candidate else f"Page {page_num}"
                    
                    # Content to hash and store
                    # Note: We keep the enrichment, but maybe we should store pure content separate?
                    # For now, sticking to the established "enriched_content" pattern for RAG.
                    enriched_content = f"Document: {doc_name} | Page: {page_num}\n\n{c.page_content}"
                    content_hash = sha256_hex(enriched_content)
                    
                    # Metadata (optional, but good practice)
                    metadata = json.dumps({
                        "page": page_num, 
                        "source": str(pdf_path),
                        "org": org,
                        "policy_type": policy_type
                    })

                    # Check if changed
                    if existing_hashes.get(i) == content_hash:
                        continue
                    
                    texts_to_embed.append(enriched_content)
                    rows_to_upsert.append({
                        "doc_name": doc_name,
                        "section": section_title, # Using section column for section_title
                        "chunk_index": i,
                        "content": enriched_content,
                        "content_hash": content_hash,
                        "metadata": metadata,
                        "page": page_num,
                        "org": org,
                        "policy_type": policy_type,
                        "section_title": section_title
                    })

                if texts_to_embed:
                    print(f"  - Embedding {len(texts_to_embed)} changed/new chunks...")
                    embeddings = get_embeddings(texts_to_embed)
                    
                    for row, emb in zip(rows_to_upsert, embeddings):
                        row["embedding"] = emb

                    print(f"  - Upserting {len(rows_to_upsert)} rows...")
                    for row in rows_to_upsert:
                         cur.execute(
                            """
                            INSERT INTO policy_chunks (
                                doc_name, section, chunk_index, content, content_hash, embedding, metadata,
                                page, org, policy_type, section_title
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (doc_name, chunk_index) DO UPDATE
                            SET
                                section = EXCLUDED.section,
                                content = EXCLUDED.content,
                                content_hash = EXCLUDED.content_hash,
                                embedding = EXCLUDED.embedding,
                                metadata = EXCLUDED.metadata,
                                page = EXCLUDED.page,
                                org = EXCLUDED.org,
                                policy_type = EXCLUDED.policy_type,
                                section_title = EXCLUDED.section_title
                            WHERE policy_chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash;
                            """,
                            (
                                row["doc_name"], 
                                row["section"], 
                                row["chunk_index"], 
                                row["content"], 
                                row["content_hash"], 
                                row["embedding"], 
                                row["metadata"],
                                row["page"],
                                row["org"],
                                row["policy_type"],
                                row["section_title"]
                            ),
                        )
                else:
                    print("  - No changes detected.")

                if current_chunk_indexes:
                    cur.execute(
                        """
                        DELETE FROM policy_chunks
                        WHERE doc_name = %s
                        AND chunk_index NOT IN (SELECT UNNEST(%s::int[]))
                        """,
                        (doc_name, current_chunk_indexes),
                    )

            conn.commit()

    print(f"Ingested {len(pdfs)} PDFs into policy_chunks.")

if __name__ == "__main__":
    main()