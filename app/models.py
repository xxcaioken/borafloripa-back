from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Table, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

event_tags_association = Table(
    'event_tags', Base.metadata,
    Column('event_id', Integer, ForeignKey('events.id'), index=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), index=True)
)

community_members = Table(
    'community_members', Base.metadata,
    Column('community_id', Integer, ForeignKey('communities.id')),
    Column('user_id', Integer, ForeignKey('users.id'))
)

user_saved_events = Table(
    'user_saved_events', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('event_id', Integer, ForeignKey('events.id'))
)

user_followed_venues = Table(
    'user_followed_venues', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('venue_id', Integer, ForeignKey('venues.id'))
)

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    endpoint = Column(String, nullable=False, unique=True)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="push_subscriptions")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    role = Column(String, default="user")
    # Preferências do onboarding (salvas após cadastro)
    pref_music = Column(String)   # JSON: ["funk","eletronico",...]
    pref_vibes = Column(String)   # JSON: ["rooftop","pet-friendly",...]
    reset_token = Column(String, nullable=True, unique=True, index=True)
    reset_token_expires = Column(DateTime, nullable=True)
    google_id = Column(String, nullable=True, unique=True, index=True)

    venues = relationship("Venue", back_populates="owner")
    communities = relationship("Community", secondary=community_members, back_populates="members")
    saved_events = relationship("Event", secondary=user_saved_events)
    followed_venues = relationship("Venue", secondary=user_followed_venues)

class Venue(Base):
    __tablename__ = "venues"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    city = Column(String, default="Florianópolis", index=True)
    lat = Column(Float, nullable=False, default=0.0)
    lng = Column(Float, nullable=False, default=0.0)
    address = Column(String)
    instagram = Column(String)
    whatsapp = Column(String)
    hours = Column(String)
    category = Column(String, default="bar")
    is_new = Column(Boolean, default=False)
    logo_url = Column(String)                       # #8 foto do local
    # Acessibilidade
    wheelchair = Column(Boolean, default=False)   # rampa/elevador
    hearing_loop = Column(Boolean, default=False) # loop magnético
    visual_aid = Column(Boolean, default=False)   # cardápio em braille/áudio
    adapted_wc = Column(Boolean, default=False)   # banheiro adaptado
    parking = Column(Boolean, default=False)      # vaga especial

    owner = relationship("User", back_populates="venues")
    events = relationship("Event", back_populates="venue")
    checkins = relationship("Checkin", back_populates="venue")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    date = Column(DateTime, nullable=False, index=True)
    vibe_status = Column(String, default="Normal")
    is_featured = Column(Boolean, default=False, index=True)
    category = Column(String, default="bar", index=True)
    # Eventos temporários (tendas, pop-ups com múltiplos parceiros)
    is_temporary = Column(Boolean, default=False)
    organizers = Column(String)  # JSON: ["Bar A","Bar B"] para eventos multi-parceiro
    cover_url = Column(String)   # #8 foto de capa do evento
    price_info = Column(String)  # ex: "Entrada: R$25 / Open bar: R$60"
    view_count = Column(Integer, default=0)  # contador de visualizações do detalhe

    venue = relationship("Venue", back_populates="events")
    tags = relationship("Tag", secondary=event_tags_association, back_populates="events")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    events = relationship("Event", secondary=event_tags_association, back_populates="tags")


class Checkin(Base):
    """#11 Hot zones — check-in anônimo por local"""
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    venue = relationship("Venue", back_populates="checkins")


class BoraReaction(Base):
    """Botão 'Bora!' — intenção de presença em evento (social proof)"""
    __tablename__ = "bora_reactions"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)  # fingerprint anônimo do browser
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class VenueVibeVote(Base):
    """Voto de usuário em uma tag de vibe para um venue — 'A galera diz que é...'"""
    __tablename__ = "venue_vibe_votes"
    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False, index=True)
    tag_name = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False)  # anônimo ou user_id como string


class Community(Base):
    """#10 Comunidade — grupos gerados por tag/preferência"""
    __tablename__ = "communities"
    id = Column(Integer, primary_key=True, index=True)
    tag_name = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    discount_code = Column(String)   # código de desconto para membros

    members = relationship("User", secondary=community_members, back_populates="communities")


# Composite indexes for common query patterns
Index('ix_bora_session_event', BoraReaction.session_id, BoraReaction.event_id, unique=True)
Index('ix_checkin_venue_time', Checkin.venue_id, Checkin.created_at)
Index('ix_event_featured_date', Event.is_featured, Event.date)
