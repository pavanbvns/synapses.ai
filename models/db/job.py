import datetime
import logging
import uuid
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Configure module logger
logger = logging.getLogger("models.db.job")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(ch)

# Create the SQLAlchemy base and engine. Adjust the database URL as needed.
DATABASE_URL = "sqlite:///./jobs.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, index=True)
    status = Column(String, index=True)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)


def create_job(job_name: str) -> int:
    """
    Create a new job record and return its ID.
    Note: This function no longer inserts a "details" column.
    """
    db = SessionLocal()
    try:
        job = Job(job_name=job_name, status="Started", start_time=datetime.datetime.utcnow())
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info("Job %d (%s) started.", job.id, job_name)
        return job.id
    except Exception as e:
        db.rollback()
        logger.exception("Error creating job: %s", e)
        raise
    finally:
        db.close()


def update_job(job_id: int, status: str):
    """
    Update the status (and end time if applicable) of a job.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = status
            if status in ["Completed", "Aborted"]:
                job.end_time = datetime.datetime.utcnow()
            db.commit()
            logger.info("Job %d updated to status: %s", job_id, status)
        else:
            logger.warning("Job ID %d not found for update.", job_id)
    except Exception as e:
        db.rollback()
        logger.exception("Error updating job %d: %s", job_id, e)
        raise
    finally:
        db.close()


# Create tables if they don't exist (for first-time startup)
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
