"""
FORCED RAG Agent (Production Stable)
- Always retrieves from Amazon Bedrock Knowledge Base
- Shows FULL retrieved context in logs
- Works with Gemini + LlamaIndex (all versions)
- No tool skipping issue
"""

from dotenv import load_dotenv
load_dotenv()

import os
import logging
from typing import List

from llama_index.retrievers.bedrock import AmazonKnowledgeBasesRetriever
from llama_index.llms.gemini import Gemini
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.settings import Settings


# -------------------------------------------------
# 1. LOGGER CONFIG (SEE RETRIEVAL + CONTEXT)
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")


# -------------------------------------------------
# 2. BEDROCK KNOWLEDGE BASE RETRIEVER
# -------------------------------------------------
retriever = AmazonKnowledgeBasesRetriever(
    knowledge_base_id=os.getenv("BEDROCK_KNOWLEDGE_BASE_ID"),
    retrieval_config={
        "vectorSearchConfiguration": {
            "numberOfResults": 2  # increase for better context
        }
    },
)


# -------------------------------------------------
# 3. GEMINI LLM (IMPORTANT: CORRECT MODEL NAME)
# -------------------------------------------------
llm = Gemini(
    model="gemini-2.5-flash",  # DO NOT use models/ prefix
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.2,
)

Settings.llm = llm


# -------------------------------------------------
# 4. QUERY NORMALIZER (Hinglish → English for better retrieval)
# -------------------------------------------------
def normalize_query(query: str) -> str:
    q = query.lower()

    if "fatty liver" in q:
        return "fatty liver treatment liver detox supplement liver health ayurvedic liver support"

    if any(word in q for word in ["kya", "kaise", "me", "hai", "de"]):
        return f"health product recommendation {query}"

    return query


# -------------------------------------------------
# 5. MULTI-HOP QUERY GENERATOR (Generate related queries)
# -------------------------------------------------
async def generate_multi_hop_queries(original_query: str) -> List[str]:
    """
    Generate related queries for multi-hop retrieval
    This helps retrieve more comprehensive context from different angles
    """
    logger.info("\n🔄 GENERATING MULTI-HOP QUERIES...\n")
    
    multi_hop_prompt = f"""Given this user query, generate 2-3 related search queries that would help find comprehensive information.

Original Query: "{original_query}"

Return ONLY the queries as a comma-separated list, no explanations.
Example: "query1, query2, query3"
"""
    
    try:
        response = await llm.achat([
            ChatMessage(role=MessageRole.USER, content=multi_hop_prompt)
        ])
        
        generated_queries_text = response.message.content
        # Parse the comma-separated queries
        generated_queries = [q.strip() for q in generated_queries_text.split(",")]
        
        logger.info("📝 Generated Multi-Hop Queries:")
        for i, q in enumerate(generated_queries, 1):
            logger.info(f"  {i}. {q}")
        
        return generated_queries
    except Exception as e:
        logger.error(f"Error generating multi-hop queries: {e}")
        return []


# -------------------------------------------------
# 6. CORE RAG FUNCTION WITH MULTI-HOP RETRIEVAL
# -------------------------------------------------
async def get_agent_response(message: str, chat_history: List[dict]):
    logger.info("=" * 80)
    logger.info("💬 NEW USER MESSAGE: %s", message)
    logger.info("=" * 80)

    # Step 1: Normalize Query
    normalized_query = normalize_query(message)
    logger.info("🌍 NORMALIZED QUERY: %s", normalized_query)

    # Step 2: Generate Multi-Hop Queries
    all_queries = [normalized_query]  # Start with original query
    generated_queries = await generate_multi_hop_queries(message)
    all_queries.extend(generated_queries)
    
    # Step 3: Retrieve Context from All Queries
    logger.info("\n🚀 STARTING MULTI-HOP RETRIEVAL FROM AMAZON BEDROCK KB...\n")
    logger.info("Total Queries to Retrieve: %d", len(all_queries))
    
    all_context_chunks = {}
    
    for query_idx, query in enumerate(all_queries, 1):
        logger.info("\n" + "=" * 80)
        logger.info(f"📍 HOP {query_idx}: Retrieving for '{query}'")
        logger.info("=" * 80)
        
        nodes = retriever.retrieve(query)
        logger.info(f"Retrieved {len(nodes)} chunks for this query\n")
        
        for i, node in enumerate(nodes, 1):
            score = getattr(node, "score", 0.0)
            text = node.node.get_content()
            metadata = getattr(node.node, "metadata", {})
            
            # Use text hash to avoid duplicates
            text_key = hash(text)
            if text_key not in all_context_chunks:
                all_context_chunks[text_key] = {
                    "text": text,
                    "score": float(score),
                    "metadata": metadata,
                    "sources": [query_idx]
                }
            else:
                # Track if chunk appeared in multiple queries
                all_context_chunks[text_key]["sources"].append(query_idx)
            
            logger.info(f"┌─ CHUNK {i} (Hop {query_idx}) ─────────────────────────")
            logger.info(f"│ Score: {float(score):.4f}")
            logger.info(f"│ Metadata: {metadata}")
            logger.info("├─ Content:")
            logger.info(f"│ {text.replace(chr(10), chr(10) + '│ ')}")
            logger.info("└────────────────────────────────────────────────\n")
    
    # Step 4: Sort chunks by score and combine
    sorted_chunks = sorted(
        all_context_chunks.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )
    
    context_chunks = [item[1]["text"] for item in sorted_chunks]
    context = "\n\n------\n\n".join(context_chunks)

    logger.info("\n" + "=" * 80)
    logger.info("📊 MULTI-HOP RETRIEVAL SUMMARY:")
    logger.info("=" * 80)
    logger.info(f"Total Unique Chunks Retrieved: {len(context_chunks)}")
    logger.info(f"Queries Used: {len(all_queries)}")
    for idx, query in enumerate(all_queries, 1):
        prefix = "🎯 Original: " if idx == 1 else "🔗 Generated: "
        logger.info(f"{prefix} {query}")
    logger.info("=" * 80)

    logger.info("\n🧠 FINAL COMBINED CONTEXT SENT TO LLM:")
    logger.info("=" * 80)
    logger.info(context if context else "NO CONTEXT RETRIEVED")
    logger.info("=" * 80)

    # Step 5: Build Prompt (STRICT RAG)
    system_prompt = (
        "You are a medical product assistant.\n"
        "Answer ONLY using the provided knowledge base context.\n"
        "If context is empty, say you don't have data.\n"
        "User may speak Hindi, Hinglish, or English.\n"
        "Respond in user's language."
    )

    user_prompt = f"""
USER QUESTION:
{message}

KNOWLEDGE BASE CONTEXT (Retrieved from multiple query angles):
{context}

INSTRUCTION:
Answer strictly based on the context above. Do not hallucinate.
Provide comprehensive answer using information from multiple sources if available.
"""

    # Step 6: Send to LLM with combined context
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=user_prompt),
    ]

    logger.info("\n🤖 SENDING MULTI-HOP CONTEXT + QUERY TO GEMINI...\n")

    response = await llm.achat(messages)

    final_answer = response.message.content

    logger.info("🤖 FINAL LLM RESPONSE:")
    logger.info(final_answer)
    logger.info("=" * 80 + "\n")

    return final_answer