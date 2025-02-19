# -*- coding: utf-8 -*-

"""main.py:
FastAPI app for the RESTful API server of lablog.
"""

__author__ = "Zhi Zi"
__email__ = "x@zzi.io"
__version__ = "20240526"

# std libs
import logging
from typing import Annotated
from json import JSONDecodeError
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from collections import defaultdict
# third party libs
from websockets.exceptions import ConnectionClosedOK
from fastapi import Depends, FastAPI, HTTPException, status, WebSocket, WebSocketDisconnect, WebSocketException, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
# this package
from .lablog import Lablog
from .server_config import server_config, UserAccessLevel
from .auth import try_authenticate, create_access_token, validate_access_token, check_access_level
from .auth import Token, TokenData, AccessLevelException
from .ws import WebSocketConnectionManager
from .database import LablogDatabaseManager
from .data_models import (
    ServerResourceNames, PostsCollection, CommentsCollection, DisplayCommentsCollection, AddOrUpdatePostData, AddOrUpdatePostResult, AddOrUpdateCommentData, AddCommentData, AddOrUpdateCommentResult, BlogData,
    DeleteCommentResult
)

lg = logging.getLogger(__name__)

ws_mgr = WebSocketConnectionManager()
lablog = Lablog()
db_mgr = LablogDatabaseManager(
    lablog=lablog,
    database_config=server_config.database)

# Rate limiting data structure
rate_limit_data = defaultdict(list)
# Spam keywords list
spam_keywords = []

def is_rate_limited(client_host: str, limit: int = 5, period: timedelta = timedelta(minutes=30)) -> bool:
    now = datetime.now()
    rate_limit_data[client_host] = [timestamp for timestamp in rate_limit_data[client_host] if now - timestamp < period]
    if len(rate_limit_data[client_host]) >= limit:
        return True
    rate_limit_data[client_host].append(now)
    return False

def is_spam(content: str) -> bool:
    return any(keyword in content.lower() for keyword in spam_keywords)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before application start, load database and scheduler
    # Load Spam keywords list
    global spam_keywords
    with open("./backend/spam_keywords.txt", "rb") as f:
        spam_keywords = f.read().decode('utf-8').split("\n")
    lg.info("Loading data from database.")
    db_mgr.load_database()
    lg.info("Starting up database manager...")
    db_mgr.start_scheduler()
    yield
    # Clean up resources and save database to file
    lg.info("Stopping database manager...")
    db_mgr.stop_scheduler()
    lg.info("Saving data to database file ")
    # Explicitly set check_hash to False to force overwriting files at exit.
    # This is nonsense if everything goes right, but if something went wrong
    # this should be able to keep some data consistency at least.
    db_mgr.save_database(check_hash=False)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config.CORS.origins,
    allow_credentials=server_config.CORS.allow_credentials,
    allow_methods=server_config.CORS.allow_methods,
    allow_headers=server_config.CORS.allow_headers,
)

# =========== RESTful API endpoints, non-priviledged ===========


@app.get("/")
async def get_resource_names() -> ServerResourceNames:
    r = [
        'token',
        'posts',
        'comments']
    return ServerResourceNames(resources=r)


@app.post("/token")
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    authenticate_result, user = try_authenticate(
        server_config.auth.users, form_data.username, form_data.password)
    if (authenticate_result is False) or (user is None):
        # don't tell the user if it is the username or the password that is wrong.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # authentication successful, create token
    access_token = create_access_token(user=user)
    return Token(**{"access_token": access_token, "token_type": "bearer"})


@app.get("/posts")
async def get_posts() -> PostsCollection:
    return lablog.get_posts()


@app.get("/posts/catagory/{catagory}")
async def get_posts_by_catagory(catagory: str) -> PostsCollection:
    return lablog.get_posts(catagory=catagory)


@app.get("/comments/{post_id}")
async def get_comments_for_post(post_id: str) -> DisplayCommentsCollection:
    if post_id not in lablog.posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    comment_id_list = lablog.posts[post_id].comments
    return lablog.get_comments_for_display(comment_id_list)


@app.post("/comments/{post_id}")
async def add_comment_for_post(post_id: str, comment_data: AddCommentData, request: Request, background_tasks: BackgroundTasks) -> AddOrUpdateCommentResult:
    client_host = request.client.host
    
    if is_rate_limited(client_host):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded. Please try again later.")
    
    if is_spam(comment_data.content):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment content detected as spam.")
    # add comment, by default, display is False before review
    comment_id = lablog.add_comment(
        name=comment_data.name, content=comment_data.content, contact_address=comment_data.contact_address, post_id=post_id, ip_address=client_host,
        display=False)
    lg.info("Added new comment \"{}\": {}".format(
            comment_id, comment_data.model_dump_json()))
    background_tasks.add_task(db_mgr.save_database)
    return AddOrUpdateCommentResult(result='success', comment_id=comment_id)


# =========== RESTful API endpoints, priviledged ===========

@app.post("/posts")
async def add_or_update_post(post_data: AddOrUpdatePostData,
                             token_data: Annotated[TokenData, Depends(validate_access_token)]) -> AddOrUpdatePostResult:
    check_access_level(token_data.access_level, UserAccessLevel.standard)
    if post_data.post_id in lablog.posts:
        post_id = post_data.post_id
        lablog.modify_post(post_id=post_data.post_id,
                           title=post_data.title,
                           abstract=post_data.abstract,
                           link=post_data.link,
                           created_timestamp=post_data.created_timestamp,
                           catagory=post_data.catagory,
                           tags=post_data.tags)
        lg.info("Modified post \"{}\": {}".format(
            post_data.post_id, post_data.model_dump_json()))
    else:
        post_id = lablog.add_post(title=post_data.title,
                                  abstract=post_data.abstract,
                                  link=post_data.link,
                                  created_timestamp=post_data.created_timestamp,
                                  catagory=post_data.catagory,
                                  tags=post_data.tags)
        lg.info("Added new post \"{}\": {}".format(post_id, post_data.title))
    db_mgr.save_database()
    return AddOrUpdatePostResult(result='success', post_id=post_id)


@app.post("/comments")
async def add_or_modify_comment(comment_data: AddOrUpdateCommentData, token_data: Annotated[TokenData, Depends(validate_access_token)]) -> AddOrUpdateCommentResult:
    check_access_level(token_data.access_level, UserAccessLevel.standard)
    if comment_data.comment_id in lablog.comments:
        comment_id = comment_data.comment_id
        lablog.modify_comment(
            comment_id=comment_id,
            name=comment_data.name,
            content=comment_data.content,
            contact_address=comment_data.contact_address,
            created_timestamp=comment_data.created_timestamp,
            ip_address=comment_data.ip_address,
            post_id=comment_data.post_id,
            display=comment_data.display,
        )
        lg.info("Modified comment \"{}\": {}".format(
            comment_id, comment_data.model_dump_json()))
    else:
        comment_id = lablog.add_comment(name=comment_data.name,
                                        content=comment_data.content,
                                        contact_address=comment_data.contact_address,
                                        created_timestamp=comment_data.created_timestamp,
                                        ip_address=comment_data.ip_address,
                                        post_id=comment_data.post_id,
                                        display=comment_data.display)
        lg.info("Added new comment \"{}\": {}".format(
            comment_id, comment_data.model_dump_json()))
    db_mgr.save_database()
    return AddOrUpdateCommentResult(result='success', comment_id=comment_id)


@app.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, token_data: Annotated[TokenData, Depends(validate_access_token)]) -> DeleteCommentResult:
    check_access_level(token_data.access_level, UserAccessLevel.standard)
    if comment_id not in lablog.comments:
        lg.warning("Attempted to delete non-existent comment \"{}\".".format(comment_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    lablog.delete_comment(comment_id)
    lg.info("Deleted comment \"{}\".".format(comment_id))
    db_mgr.save_database()
    return DeleteCommentResult(result='success', comment_id=comment_id)


@app.get("/management/data")
async def get_management_data(token_data: Annotated[TokenData, Depends(validate_access_token)]) -> BlogData:
    check_access_level(token_data.access_level, UserAccessLevel.standard)
    return lablog.get_management_data()

