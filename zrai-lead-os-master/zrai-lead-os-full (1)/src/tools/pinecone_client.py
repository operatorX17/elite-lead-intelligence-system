"""
Pinecone client for vector store operations.
Requirements: 10 (RAG & Playbooks), 16.1-16.3
"""

from typing import Dict, Any, List, Optional
import logging

from pinecone import Pinecone

from src.config import load_config


logger = logging.getLogger(__name__)


class PineconeClient:
    """
    Pinecone client wrapper for ZRAI Lead OS.
    
    Requirements:
    - 10: Use playbooks table + vector store for RAG
    - 16.1: Retrieve relevant playbook snippets by niche, tier, channel
    - 16.2: Version playbooks and tie to run_id
    - 16.3: Include outreach_examples, objection_handling, compliance_rules, niche_notes
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
    ):
        config = load_config()
        
        self._api_key = api_key or config.pinecone.api_key
        self._index_name = index_name or config.pinecone.index_name
        
        # Initialize Pinecone
        self._pc = Pinecone(api_key=self._api_key)
        self._index = self._pc.Index(self._index_name)
    
    def upsert_playbook(
        self,
        playbook_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        """
        Upsert a playbook into the vector store.
        Requirements: 16.2
        """
        logger.info(f"Upserting playbook: {playbook_id}")
        
        self._index.upsert(
            vectors=[{
                "id": playbook_id,
                "values": embedding,
                "metadata": metadata,
            }]
        )
    
    def query_playbooks(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query playbooks by embedding similarity.
        Requirements: 16.1
        """
        logger.info(f"Querying playbooks (top_k={top_k})")
        
        results = self._index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
        )
        
        return [
            {
                "id": match["id"],
                "score": match["score"],
                "metadata": match.get("metadata", {}),
            }
            for match in results.get("matches", [])
        ]
    
    def get_playbooks_by_niche(
        self,
        query_embedding: List[float],
        niche: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get playbooks filtered by niche.
        Requirements: 16.1
        """
        return self.query_playbooks(
            query_embedding=query_embedding,
            top_k=top_k,
            filter={"niche": {"$eq": niche}},
        )
    
    def get_playbooks_by_tier(
        self,
        query_embedding: List[float],
        tier: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get playbooks filtered by tier.
        Requirements: 16.1
        """
        return self.query_playbooks(
            query_embedding=query_embedding,
            top_k=top_k,
            filter={"tier": {"$eq": tier}},
        )
    
    def get_playbooks_by_channel(
        self,
        query_embedding: List[float],
        channel: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get playbooks filtered by channel.
        Requirements: 16.1
        """
        return self.query_playbooks(
            query_embedding=query_embedding,
            top_k=top_k,
            filter={"channel": {"$eq": channel}},
        )
    
    def get_outreach_examples(
        self,
        query_embedding: List[float],
        niche: Optional[str] = None,
        tier: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get outreach examples for RAG.
        Requirements: 10, 16.3
        """
        filter_dict = {"content_type": {"$eq": "outreach_example"}}
        
        if niche:
            filter_dict["niche"] = {"$eq": niche}
        if tier:
            filter_dict["tier"] = {"$eq": tier}
        
        return self.query_playbooks(
            query_embedding=query_embedding,
            top_k=top_k,
            filter=filter_dict,
        )
    
    def get_objection_handling(
        self,
        query_embedding: List[float],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get objection handling snippets for RAG.
        Requirements: 10, 16.3
        """
        return self.query_playbooks(
            query_embedding=query_embedding,
            top_k=top_k,
            filter={"content_type": {"$eq": "objection_handling"}},
        )
    
    def get_compliance_rules(
        self,
        query_embedding: List[float],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get compliance rules for RAG.
        Requirements: 10, 16.3
        """
        return self.query_playbooks(
            query_embedding=query_embedding,
            top_k=top_k,
            filter={"content_type": {"$eq": "compliance_rule"}},
        )
    
    def delete_playbook(self, playbook_id: str) -> None:
        """Delete a playbook from the vector store."""
        logger.info(f"Deleting playbook: {playbook_id}")
        self._index.delete(ids=[playbook_id])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return self._index.describe_index_stats()
