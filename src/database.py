from sqlalchemy import create_engine, Column, BigInteger, Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
import os
from typing import Dict

DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

# Create engine
engine = create_engine(DATABASE_URL)

# create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base that will be used for tables creation
Base = declarative_base()


# Define Table model
class Message(Base):
    __tablename__ = "messages"

    message_id = Column(BigInteger, primary_key=True)
    group_id = Column(String, index=True, nullable=False)
    date = Column(DateTime)
    sender_id = Column(BigInteger)
    channel_id = Column(BigInteger)
    text = Column(Text)
    views = Column(Integer, nullable=True)
    replies = Column(Integer, nullable=True)
    raw_json = Column(JSON, nullable=True)

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")

# insert rows in message table
def insert_message_sync(row: Dict):
    db = SessionLocal()

    try:
        db.add(
            Message(
                message_id = row.get("message_id"),
                group_id = row.get("group_id"),
                date = row.get("date"),
                sender_id = row.get("sender_id"),
                channel_id = row.get("channel_id"),
                text = row.get("text"),
                views = row.get("views"),
                replies = row.get("replies"),
                raw_json = row.get("raw_json"),
            )
        )
        db.commit()
    
    except IntegrityError:
        db.rollback()
        print(f"Message {row.get('message_id')} already exists in the database.")

    except Exception as e:
        db.rollback()
        print(f"Error inserting message {row.get('message_id')}: {e}")
        raise e
    finally:
        db.close()


    

