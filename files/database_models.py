# app/models/database.py
"""
Complete Database Models for Production ChatBot
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Integer, Float, Boolean, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# ==================== USER & AUTH MODELS ====================

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth users
    full_name = Column(String)
    
    # User tier and status
    tier = Column(String, default="free", index=True)  # free, pro, enterprise
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
    
    # Preferences
    preferences = Column(JSON, default={})  # UI preferences, default model, etc.
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("Usage", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, tier={self.tier})>"

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String, nullable=False)  # User-defined name
    key_hash = Column(String, unique=True, nullable=False, index=True)  # SHA256 hash
    key_prefix = Column(String, nullable=False)  # First 8 chars for display
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)  # Optional expiration
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    __table_args__ = (
        Index('ix_api_keys_user_active', 'user_id', 'is_active'),
    )

    def __repr__(self):
        return f"<APIKey(name={self.name}, user_id={self.user_id})>"

# ==================== CONVERSATION MODELS ====================

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String)  # Auto-generated from first message or user-set
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    metadata = Column(JSON, default={})  # Tags, folder, custom fields
    model = Column(String)  # Model used for this conversation
    
    # Status
    is_archived = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    
    __table_args__ = (
        Index('ix_conversations_user_created', 'user_id', 'created_at'),
        Index('ix_conversations_user_updated', 'user_id', 'updated_at'),
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title})>"

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message content
    role = Column(String, nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    
    # Tool calls (for assistant messages)
    tool_calls = Column(JSON)  # Array of tool call objects
    tool_call_id = Column(String)  # For tool response messages
    
    # Metrics
    tokens = Column(Integer)
    cost = Column(Float)  # Cost in USD
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Metadata
    metadata = Column(JSON, default={})  # Model, temperature, etc.
    
    # User feedback
    feedback = Column(JSON)  # thumbs up/down, custom feedback
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    __table_args__ = (
        Index('ix_messages_conversation_created', 'conversation_id', 'created_at'),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"

# ==================== USAGE & BILLING MODELS ====================

class Usage(Base):
    __tablename__ = "usage"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Time period
    date = Column(DateTime, nullable=False, index=True)  # Granularity: hour or day
    
    # Usage metrics
    requests_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    
    # Cost
    cost = Column(Float, default=0.0)
    
    # Provider breakdown
    provider_breakdown = Column(JSON, default={})  # {"openai": 1000, "anthropic": 500}
    
    # Relationships
    user = relationship("User", back_populates="usage_records")
    
    __table_args__ = (
        Index('ix_usage_user_date', 'user_id', 'date'),
    )

    def __repr__(self):
        return f"<Usage(user_id={self.user_id}, date={self.date}, tokens={self.tokens_used})>"

# ==================== TOOL & PLUGIN MODELS ====================

class ToolExecution(Base):
    __tablename__ = "tool_executions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"))
    
    # Tool info
    tool_name = Column(String, nullable=False, index=True)
    server_name = Column(String)  # MCP server name
    
    # Execution
    arguments = Column(JSON, nullable=False)
    result = Column(JSON)
    
    # Status
    status = Column(String, nullable=False)  # success, error, timeout
    error_message = Column(Text)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)  # Milliseconds
    
    __table_args__ = (
        Index('ix_tool_executions_conversation', 'conversation_id'),
        Index('ix_tool_executions_tool_status', 'tool_name', 'status'),
    )

    def __repr__(self):
        return f"<ToolExecution(tool={self.tool_name}, status={self.status})>"

# ==================== FEEDBACK & ANALYTICS MODELS ====================

class ConversationFeedback(Base):
    __tablename__ = "conversation_feedback"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    
    # Feedback type
    feedback_type = Column(String, nullable=False)  # thumbs_up, thumbs_down, flag, custom
    
    # Details
    rating = Column(Integer)  # 1-5 stars
    comment = Column(Text)
    tags = Column(JSON)  # ["helpful", "accurate", "fast"]
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_feedback_conversation', 'conversation_id'),
        Index('ix_feedback_type_created', 'feedback_type', 'created_at'),
    )

class SystemEvent(Base):
    __tablename__ = "system_events"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Event details
    event_type = Column(String, nullable=False, index=True)  # error, warning, info
    category = Column(String, index=True)  # auth, llm, mcp, database
    
    # Message
    message = Column(Text, nullable=False)
    details = Column(JSON)
    
    # Context
    user_id = Column(String, index=True)
    conversation_id = Column(String)
    request_id = Column(String, index=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('ix_events_type_created', 'event_type', 'created_at'),
        Index('ix_events_category_created', 'category', 'created_at'),
    )

# ==================== RATE LIMITING MODELS ====================

class RateLimitRule(Base):
    __tablename__ = "rate_limit_rules"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Rule definition
    tier = Column(String, nullable=False, index=True)  # free, pro, enterprise
    resource = Column(String, nullable=False)  # requests, tokens, conversations
    
    # Limits
    limit_value = Column(Integer, nullable=False)
    window_seconds = Column(Integer, nullable=False)  # Time window
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_rate_limits_tier_resource', 'tier', 'resource'),
    )
