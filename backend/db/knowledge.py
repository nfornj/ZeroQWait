"""
Agent category aliases, knowledge, agent memory, and synonym operations.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import or_, func, desc

# Import the single source of truth for database connections
from database import SessionLocal
from models import (
    User, Shop, Queue, QueueItem, ShopEmployee, EmployeeShift, 
    ShopService, ShopCustomer, DailyAnalytics, ConversationHistory, CategoryAlias, 
    LearnedSynonym, AgentKnowledge, AgentMemory
)
import schemas



class KnowledgeMixin:
    # --- Agent / Category Support ---
    def get_all_shops(self) -> List[Dict]:
        return self.get_shops(limit=1000)

    def get_category_aliases(self) -> List[Dict]:
        db = self.get_session()
        try:
            aliases = db.query(CategoryAlias).all()
            return [self._model_to_dict(a) for a in aliases]
        except Exception as e:
            print(f"Error fetching aliases: {e}")
            return []
        finally:
            db.close()

    def add_category(self, category_key: str, display_name: str, aliases: List[str]):
        db = self.get_session()
        try:
            for alias in aliases:
                exists = db.query(CategoryAlias).filter(
                    CategoryAlias.category_key == category_key,
                    CategoryAlias.alias == alias
                ).first()
                
                if not exists:
                    obj = CategoryAlias(category_key=category_key, alias=alias)
                    db.add(obj)
            db.commit()
        except Exception as e:
            print(f"Error adding category: {e}")
        finally:
            db.close()

    def get_agent_knowledge(self, key: str) -> Optional[Dict]:
        db = self.get_session()
        try:
            item = db.query(AgentKnowledge).filter(AgentKnowledge.key == key).first()
            return self._model_to_dict(item) if item else None
        except Exception:
            return None
        finally:
            db.close()

    def get_all_agent_knowledge(self) -> List[Dict]:
        db = self.get_session()
        try:
            items = db.query(AgentKnowledge).all()
            return [self._model_to_dict(item) for item in items]
        except Exception:
            return []
        finally:
            db.close()

    def upsert_agent_knowledge(self, key: str, content: str, description: str = None) -> Dict:
        db = self.get_session()
        try:
            item = db.query(AgentKnowledge).filter(AgentKnowledge.key == key).first()
            if item:
                item.content = content
                if description:
                    item.description = description
                item.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(item)
            else:
                item = AgentKnowledge(
                    key=key,
                    content=content,
                    description=description
                )
                db.add(item)
                db.commit()
                db.refresh(item)
            return self._model_to_dict(item)
        finally:
            db.close()

    # --- Agent Memory (tenant-scoped, extensible for vector search) ---
    def add_agent_memory(
        self,
        shop_id: int,
        content: str,
        memory_type: str = "episodic",
        user_id: Optional[int] = None,
        source: Optional[str] = None,
        importance_score: float = 0.5,
        memory_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        db = self.get_session()
        try:
            item = AgentMemory(
                shop_id=shop_id,
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                source=source,
                importance_score=max(0.0, min(1.0, importance_score)),
                memory_meta=memory_meta or {},
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return self._model_to_dict(item)
        finally:
            db.close()

    def get_agent_memories(
        self,
        shop_id: int,
        memory_type: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict]:
        db = self.get_session()
        try:
            query = db.query(AgentMemory).filter(
                AgentMemory.shop_id == shop_id,
                AgentMemory.is_active == True,
            )
            if memory_type:
                query = query.filter(AgentMemory.memory_type == memory_type)
            if user_id is not None:
                query = query.filter(
                    or_(
                        AgentMemory.user_id == user_id,
                        AgentMemory.user_id.is_(None),
                    )
                )

            items = query.order_by(
                desc(AgentMemory.importance_score),
                desc(AgentMemory.created_at),
            ).limit(limit).all()
            return [self._model_to_dict(item) for item in items]
        finally:
            db.close()

    def search_agent_memories(
        self,
        shop_id: int,
        query_text: str,
        memory_type: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict]:
        db = self.get_session()
        try:
            query = db.query(AgentMemory).filter(
                AgentMemory.shop_id == shop_id,
                AgentMemory.is_active == True,
                AgentMemory.content.ilike(f"%{query_text}%"),
            )
            if memory_type:
                query = query.filter(AgentMemory.memory_type == memory_type)
            if user_id is not None:
                query = query.filter(
                    or_(
                        AgentMemory.user_id == user_id,
                        AgentMemory.user_id.is_(None),
                    )
                )

            items = query.order_by(
                desc(AgentMemory.importance_score),
                desc(AgentMemory.created_at),
            ).limit(limit).all()
            return [self._model_to_dict(item) for item in items]
        finally:
            db.close()

    def touch_agent_memory(self, memory_id: int) -> Optional[Dict]:
        db = self.get_session()
        try:
            item = db.query(AgentMemory).filter(AgentMemory.id == memory_id).first()
            if not item:
                return None
            item.last_accessed_at = datetime.utcnow()
            db.commit()
            db.refresh(item)
            return self._model_to_dict(item)
        finally:
            db.close()

    def get_learned_synonyms(self) -> List[Dict]:
        db = self.get_session()
        try:
            synonyms = db.query(LearnedSynonym).all()
            return [self._model_to_dict(s) for s in synonyms]
        except Exception:
            return []
        finally:
            db.close()

    def add_learned_synonym(self, query_term: str, category: str, full_query: str = None, timestamp: str = None):
        db = self.get_session()
        try:
            exists = db.query(LearnedSynonym).filter(
                LearnedSynonym.query_term == query_term,
                LearnedSynonym.category == category
            ).first()
            
            if not exists:
                created_at_val = datetime.utcnow()
                if isinstance(timestamp, str):
                    try:
                        created_at_val = datetime.fromisoformat(timestamp)
                    except:
                        pass
                        
                obj = LearnedSynonym(
                    query_term=query_term,
                    category=category,
                    full_query=full_query,
                    created_at=created_at_val
                )
                db.add(obj)
                db.commit()
        finally:
            db.close()

