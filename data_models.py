# -*- coding: utf-8 -*-

"""data_models.py:
This module defines the data models used by lablog-backend.
"""

__author__ = "Zhi Zi"
__email__ = "x@zzi.io"
__version__ = "20240526"

# std
from typing import Optional
from enum import Enum
# third party
from pydantic import BaseModel, Field


# =========== Data models for Application

class PostMetadata(BaseModel):
    # This model stores all metadata for a single blog post
    title: str
    abstract: str
    link: str
    created_timestamp: float
    catagory: str
    tags: list[str]
    comments: list[str]
    # this may look duplicate, because we typically will only access PostMetadata by its id, in some superior data structure such as BlogData, and in theory any function or method that needs this id information can receive it from its caller, but this is here for convenience, because sometimes we don't want to bother passing additional parameters just for id, in that case we can directly read it from our convenient PostMetadata object, and all we pay is just a little bit more storage space and bandwidth... Yummy!
    post_id: str


class CommentData(BaseModel):
    # This model stores all data and metadata for a single comment
    name: str
    content: str
    contact_address: str
    created_timestamp: float
    ip_address: str
    # This is here for the same reason for PostMetadata
    comment_id: str
    # This is used to refer to the post it belongs
    post_id: str
    # Whether the comment should be displayed, comment is hidden if not approved, etc.
    display: bool


class BlogData(BaseModel):
    # This model contains all data used in lablog that needs persistence
    posts: dict[str, PostMetadata]
    comments: dict[str, CommentData]


# =========== Data models for Server

class ServerResourceNames(BaseModel):
    # Used to indicate available resources in RESTful root dir
    resources: list[str]


class AddOrUpdatePostData(BaseModel):
    # if post_id is supplied and it already exists in database, then this is an update to post
    # if not, then we will create a new post record,
    # even if a same post with a different id is already present
    post_id: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    link: Optional[str] = None
    created_timestamp: Optional[float] = None
    catagory: Optional[str] = None
    tags: Optional[list[str]] = None


class AddOrUpdatePostResult(BaseModel):
    result: str
    post_id: str


class AddOrUpdateCommentData(BaseModel):
    # This model is used for managing comment data
    # if comment_id is supplied and it already exists in database, then this is an update
    # if not, then we will create a new comment record,
    # even if an identical comment is already present
    comment_id: Optional[str] = None
    name: Optional[str] = None
    content: Optional[str] = None
    contact_address: Optional[str] = None
    created_timestamp: Optional[float] = None
    ip_address: Optional[str] = None
    post_id: Optional[str] = None
    display: Optional[bool] = None


class AddCommentData(BaseModel):
    # This model is used for users to post comment to a post
    name: str
    content: str
    contact_address: str


class AddOrUpdateCommentResult(BaseModel):
    result: str
    comment_id: str

class DeleteCommentResult(BaseModel):
    result: str
    comment_id: str

class PostsCollection(BaseModel):
    # This model is used when user requested a bunch of posts,
    # filtered and sorted by some critiria
    posts: list[PostMetadata]


class DisplayCommentData(BaseModel):
    # Diffrerent from a post, comment data stored contains confidential information
    # of the commenter, thus when user requested for comment data, some comment data should
    # not be returned, only those data for display should be returned
    name: str
    content: str
    # truncate time to seconds since frontend only needs to display time in seconds, this saves a bit of bandwidth.
    created_timestamp: int


class DisplayCommentsCollection(BaseModel):
    # This model is used when user requested a bunch of comments for display,
    # filtered and sorted by some critiria
    comments: list[DisplayCommentData]


class CommentsCollection(BaseModel):
    # This model is used when priviledged user requested a bunch of comment data,
    # for managing comments
    comments: list[CommentData]
