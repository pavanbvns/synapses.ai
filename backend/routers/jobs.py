# backend/routers/jobs.py

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body  # Added Body
from sqlalchemy.orm import Session

# Assuming JobResponse, etc. are defined as before
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# Database imports - uses models/db/job.py structure
# Ensure Job model has task_type, user details, description, result_summary columns
from backend.models.db.job import Job, SessionLocal, create_job, update_job

# --- Logger Setup ---
# ... (logger setup remains the same) ...
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- FastAPI Router ---
router = APIRouter()  # Prefix set in main.py


# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic Models ---
# Request model for creating a job record
class JobCreateRequest(BaseModel):
    job_name: str = Field(..., min_length=1)
    task_type: str = Field(..., min_length=1)
    description: Optional[str] = None
    submitted_by_name: Optional[str] = None
    submitted_by_email: Optional[str] = None  # Use Optional[str]


# Response model for single job (can reuse from GET list)
class JobResponse(BaseModel):
    id: int
    job_name: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    submitted_by_name: Optional[str] = None
    submitted_by_email: Optional[str] = None
    description: Optional[str] = None
    result_summary: Optional[str] = None

    class Config:
        orm_mode = True


# Response model for list of jobs (can reuse from GET list)
class JobListResponse(BaseModel):
    jobs: List[JobResponse]


# Request model for updating job status/result
class JobStatusUpdateRequest(BaseModel):
    status: str
    result_summary: Optional[str] = None


# --- API Endpoints ---


# GET / (List Jobs - keep as before)
@router.get("/", response_model=JobListResponse)
async def get_jobs_list(
    user_name: Optional[str] = Query(
        None, description="Filter jobs by submitter's name."
    ),
    email: Optional[str] = Query(None, description="Filter jobs by submitter's email."),
    limit: int = Query(100, description="Max jobs to return.", ge=1, le=500),
    skip: int = Query(0, description="Jobs to skip (for pagination).", ge=0),
    db: Session = Depends(get_db),
):
    """Retrieves a list of jobs, optionally filtered by user."""
    # ...(Implementation remains the same as before)...
    logger.info(
        f"API: Request for job list. Filters: email='{email}', name='{user_name}' limit={limit}, skip={skip}"
    )
    try:
        query = db.query(Job)
        if email:
            query = query.filter(Job.submitted_by_email == email)
        if user_name:
            query = query.filter(Job.submitted_by_name == user_name)
        total_count = query.count()
        jobs_query = query.order_by(Job.start_time.desc()).offset(skip).limit(limit)
        jobs = jobs_query.all()
        logger.info(f"API: Returning {len(jobs)} jobs (total matching: {total_count})")
        return JobListResponse(jobs=jobs)
    except Exception as e:
        logger.exception(f"API: Error querying jobs list: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error retrieving job list."
        )


# --- NEW: POST / (Create Job Record) ---
@router.post("/", response_model=JobResponse, status_code=201)
async def create_new_job_record(
    job_data: JobCreateRequest = Body(...), db: Session = Depends(get_db)
):
    """Creates a job record in the database and returns its details."""
    logger.info(
        f"API: Received request to create job record for task: {job_data.task_type}"
    )
    try:
        # Call the DB function to create the job
        # Assuming create_job now correctly accepts these args and returns ID
        job_id = create_job(
            job_name=job_data.job_name,
            task_type=job_data.task_type,
            submitted_by_name=job_data.submitted_by_name,
            submitted_by_email=job_data.submitted_by_email,
            description=job_data.description,
        )

        if job_id is None:
            logger.error("API: Failed to create job record in DB.")
            raise HTTPException(
                status_code=500, detail="Failed to create job record in database."
            )

        # Fetch the newly created job to return its details
        new_job = db.query(Job).filter(Job.id == job_id).first()
        if not new_job:
            logger.error(f"API: Job created (ID: {job_id}) but couldn't be retrieved.")
            raise HTTPException(
                status_code=500, detail="Job created but failed to retrieve details."
            )

        logger.info(f"API: Successfully created job record ID: {job_id}")
        return new_job  # Pydantic converts Job object based on JobResponse schema
    except Exception as e:
        logger.exception(f"API: Error creating new job record: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error creating job record: {str(e)}",
        )


# --- NEW: PUT /{job_id}/status (Update Job Status/Result) ---
@router.put("/{job_id}/status", response_model=JobResponse)
async def update_job_record_status(
    job_id: int,
    status_update: JobStatusUpdateRequest = Body(...),
    db: Session = Depends(get_db),
):
    """Updates the status and optionally the result summary of a job."""
    logger.info(
        f"API: Received request to update status for job ID {job_id} to '{status_update.status}'"
    )
    try:
        # Call the DB function to update the job
        update_job(
            job_id=job_id,
            status=status_update.status,
            result_summary=status_update.result_summary,
        )

        # Fetch the updated job to return its details
        updated_job = db.query(Job).filter(Job.id == job_id).first()
        if not updated_job:
            logger.error(
                f"API: Job status updated (ID: {job_id}) but couldn't be retrieved."
            )
            # Should not happen if update_job doesn't raise error, but handle anyway
            raise HTTPException(status_code=404, detail="Job not found after update.")

        logger.info(f"API: Successfully updated job status for ID: {job_id}")
        return updated_job
    except Exception as e:
        logger.exception(f"API: Error updating job status for ID {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error updating job status: {str(e)}",
        )
