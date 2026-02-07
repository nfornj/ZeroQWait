from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base

class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'tool'
    content = Column(Text, nullable=False)
    tool_call_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
