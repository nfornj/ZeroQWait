from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON
from sqlalchemy.types import UserDefinedType
from datetime import datetime
from database import Base


class _Vector(UserDefinedType):
    """Minimal SQLAlchemy type that maps to PostgreSQL vector(n)."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"

    def bind_expression(self, bindvalue):
        return bindvalue

    class comparator_factory(UserDefinedType.Comparator):
        def cosine_distance(self, other):
            from sqlalchemy import literal_column
            return literal_column(f"({self.expr} <=> {other})")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'tool'
    content = Column(Text, nullable=False)
    tool_call_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Semantic embedding (populated by background indexer or at write time)
    embedding = Column(_Vector(384), nullable=True)

class CategoryAlias(Base):
    __tablename__ = "category_aliases"
    
    id = Column(Integer, primary_key=True, index=True)
    category_key = Column(String, index=True, nullable=False)
    alias = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LearnedSynonym(Base):
    __tablename__ = "learned_synonyms"
    
    id = Column(Integer, primary_key=True, index=True)
    query_term = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    full_query = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentKnowledge(Base):
    __tablename__ = "agent_knowledge"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    content = Column(Text, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=True)
    memory_type = Column(String, index=True, nullable=False, default="episodic")
    content = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    importance_score = Column(Float, nullable=False, default=0.5)
    memory_meta = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_accessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
