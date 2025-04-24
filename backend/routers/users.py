# backend/routers/users.py

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field  # Use Pydantic for validation

# Database imports - adjust path if Base/SessionLocal/engine are centralized
from backend.models.db.user import User, SessionLocal, get_user_by_email, create_user

# --- Logger Setup ---
logger = logging.getLogger(__name__)
# Assuming logger configured in main or via logging setup
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- FastAPI Router ---
router = APIRouter(
    prefix="/users",  # Base path for user-related endpoints
    tags=["Users"],  # Tag for OpenAPI documentation grouping
    responses={404: {"description": "Not found"}},  # Default response for not found
)


# --- Database Dependency ---
# defines a dependency to get a DB session for requests
def get_db():
    db = SessionLocal()
    try:
        yield db  # provides the session to the endpoint function
    finally:
        db.close()  # ensures the session is closed after the request


# --- Pydantic Models for Request/Response ---


class UserBase(BaseModel):
    # basic user schema, enforcing email format
    email: EmailStr
    name: str = Field(
        ..., min_length=1
    )  # name is required and must have at least 1 char

    class Config:
        # enables ORM mode to work directly with SQLAlchemy models
        orm_mode = True  # Pydantic V1 style, use from_attributes = True in V2


class UserCreate(UserBase):
    # schema specifically for creating a user (inherits from UserBase)
    pass


class UserResponse(UserBase):
    # schema for returning user data (includes ID)
    id: int


# --- API Endpoints ---


@router.get("/lookup_by_email", response_model=UserResponse)
async def lookup_user(
    email: EmailStr = Query(..., description="Email address to look up."),
    db: Session = Depends(get_db),  # injects DB session
):
    """
    Looks up a user by their email address.
    Returns user details if found, otherwise returns 404 Not Found.
    """
    logger.info(f"API: Received lookup request for email: {email}")
    db_user = get_user_by_email(db, email=email)
    if db_user is None:
        logger.warning(f"API: User not found for email: {email}")
        # raises standard HTTP 404 exception if user not found
        raise HTTPException(status_code=404, detail="User not found")
    logger.info(f"API: Found user: ID {db_user.id} for email: {email}")
    # Pydantic automatically converts the SQLAlchemy object to JSON based on UserResponse
    return db_user


@router.post(
    "/register", response_model=UserResponse, status_code=201
)  # 201 Created status
async def register_user(
    user_data: UserCreate = Body(...),  # expects user data in request body
    db: Session = Depends(get_db),  # injects DB session
):
    """
    Registers a new user.
    Checks if email already exists. If not, creates the user and returns details.
    Returns 409 Conflict if email already exists.
    Returns 400 Bad Request for invalid input data (handled by Pydantic).
    """
    logger.info(f"API: Received registration request for email: {user_data.email}")
    # first check if user already exists with this email
    existing_user = get_user_by_email(db, email=user_data.email)
    if existing_user:
        logger.warning(
            f"API: Registration failed - email already exists: {user_data.email}"
        )
        # raises HTTP 409 Conflict if email is already registered
        raise HTTPException(status_code=409, detail="Email already registered")

    # attempt to create the new user in the database
    try:
        new_user = create_user(db, name=user_data.name, email=user_data.email)
        # check if creation succeeded (create_user returns None on IntegrityError)
        if new_user is None:
            # This case should theoretically be caught by the check above, but handles race conditions
            logger.error(
                f"API: User creation race condition or unexpected DB error for email: {user_data.email}"
            )
            raise HTTPException(
                status_code=500,
                detail="Could not create user due to a database conflict.",
            )

        logger.info(
            f"API: Successfully registered user: ID {new_user.id}, Email: {new_user.email}"
        )
        # return the newly created user details
        return new_user
    except Exception as e:
        # handle unexpected database errors during creation
        logger.exception(
            f"API: Unexpected error during user registration for {user_data.email}: {e}"
        )
        raise HTTPException(
            status_code=500, detail=f"Internal server error during user creation: {e}"
        )
