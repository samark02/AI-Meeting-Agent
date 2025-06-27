from typing import List, Dict, Any
from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
import nltk
from nltk.tokenize import word_tokenize
import numpy as np
from pytz import timezone 
from datetime import datetime

class RAGSystem:
    def __init__(self, db_name: str = "rag_database.db"):
        """Initialize RAG system with Milvus Lite and necessary models."""
        # Initialize Milvus client
        self.client = MilvusClient(db_name)
        
        # Initialize models
        self.encoder = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        # Collection settings
        self.collection_name = "rag_collection"
        self.vector_dim = 768  # Dimension of sentence-transformer embeddings
        
        # Initialize BM25 components
        self.bm25 = None
        self.all_chunks = []
        self.tokenized_chunks = []
        
        # Create collection if it doesn't exist
        self._ensure_collection_exists()
        
        # Load existing data if any
        self._load_existing_data()

    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist."""
        if not self.client.has_collection(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                dimension=self.vector_dim,
                primary_field_name="id",
                vector_field_name="embedding"
            )

    def _load_existing_data(self):
        """Load existing data from collection into BM25 index."""
        if self.client.has_collection(self.collection_name):
            try:
                count_query = self.client.query(
                    collection_name=self.collection_name,
                    filter="",
                    output_fields=["count(*)"],
                    limit=1
                )
                
                if count_query and count_query[0]['count(*)'] > 0:
                    existing_data = self.client.query(
                        collection_name=self.collection_name,
                        filter="",
                        output_fields=["text"],
                        limit=count_query[0]['count(*)']
                    )
                    
                    if existing_data:
                        for item in existing_data:
                            text = item['text']
                            self.all_chunks.append(text)
                            self.tokenized_chunks.append(word_tokenize(text.lower()))
                        
                        self.bm25 = BM25Okapi(self.tokenized_chunks)
                        print(f"Loaded {len(self.all_chunks)} existing chunks from the database")
            except Exception as e:
                print(f"Error loading existing data: {str(e)}")
                self.bm25 = BM25Okapi([[]])

    def chunk_text(self, text: str, client_name:str, chunk_size: int = 50, overlap: int = 10) -> List[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        date = datetime.now(timezone("Asia/Kolkata")).strftime('%Y-%m-%d')
        for i in range(0, len(words), chunk_size - overlap):
            chunk = client_name+' '+date+'\n '.join(words[i:i + chunk_size])
            chunks.append(chunk)
            
        return chunks

    def add_text(self, text: str, client_name: str, source_name: str = "custom_input"):
        """Add a new text string to the knowledge base."""
        try:
            # Process the content
            chunks = self.chunk_text(text,client_name)
            embeddings = self.encoder.encode(chunks)
            
            # Prepare data for insertion
            data = []
            start_id = len(self.all_chunks)
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                data.append({
                    "id": start_id + i,
                    "embedding": embedding,
                    "text": chunk,
                    "source": source_name
                })
                
                # Add to BM25 components
                self.all_chunks.append(chunk)
                self.tokenized_chunks.append(word_tokenize(chunk.lower()))
            
            # Insert into Milvus
            self.client.insert(
                collection_name=self.collection_name,
                data=data
            )
            
            # Update BM25 index
            self.bm25 = BM25Okapi(self.tokenized_chunks)
            
            print(f"Successfully added text from source: {source_name}")
            print(f"Added {len(chunks)} new chunks to the knowledge base")
            
        except Exception as e:
            print(f"Error processing text: {str(e)}")

    def hybrid_search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector similarity and BM25."""
        if not self.all_chunks:
            return []
            
        # Vector search
        query_embedding = self.encoder.encode([query])
        vector_results = self.client.search(
            collection_name=self.collection_name,
            data=query_embedding,
            limit=3,
            output_fields=["text", "source"]
        )
        
        # BM25 search
        tokenized_query = word_tokenize(query.lower())
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_bm25_indices = np.argsort(bm25_scores)[-3:][::-1]
        
        # Combine results
        candidates = []
        
        # Add vector search results
        for result in vector_results[0]:
            candidates.append({
                'text': result['entity']['text'],
                'source': result['entity']['source'],
                'score_type': 'vector',
                'score': 1 - result['distance']
            })
        
        # Add BM25 results
        for idx in top_bm25_indices:
            candidates.append({
                'text': self.all_chunks[idx],
                'score_type': 'bm25',
                'score': bm25_scores[idx]
            })
        
        # Remove duplicates (keeping the higher-scored version)
        seen_texts = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate['text'] not in seen_texts:
                seen_texts.add(candidate['text'])
                unique_candidates.append(candidate)
        
        # Rerank with cross-encoder
        rerank_pairs = [[query, candidate['text']] for candidate in unique_candidates]
        rerank_scores = self.cross_encoder.predict(rerank_pairs)
        
        # Combine results with rerank scores
        for candidate, rerank_score in zip(unique_candidates, rerank_scores):
            candidate['rerank_score'] = float(rerank_score)
        
        # Sort by rerank score and return top_k
        ranked_results = sorted(unique_candidates, key=lambda x: x['rerank_score'], reverse=True)
        return ranked_results[:top_k]

    def get_collection_stats(self):
        """Get statistics about the current knowledge base."""
        try:
            total_count = self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["count(*)"],
                limit=1
            )
            
            unique_sources = self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["source"],
                limit=1000
            )
            
            return {
                "total_chunks": total_count[0]['count(*)'] if total_count else 0,
                "unique_sources": len(set(doc['source'] for doc in unique_sources)) if unique_sources else 0
            }
        except Exception as e:
            print(f"Error getting stats: {str(e)}")
            return {"total_chunks": 0, "unique_sources": 0}