# -*- coding: utf-8 -*-

"""lablog.py:
This module defines the operations of lablog.

[TODO]: seperate file reads and writes to database.py
"""

__author__ = "Zhi Zi"
__email__ = "x@zzi.io"
__version__ = "20240526"

# std libs
import time
import json
import hashlib
import logging
from typing import Optional, Callable
# third party libs
import uuid
# this project
from .data_models import (
    PostsCollection,
    CommentsCollection,
    DisplayCommentsCollection,
    PostMetadata,
    CommentData,
    DisplayCommentData,
    BlogData
)

lg = logging.getLogger(__name__)


class PostFilter:
    """
    This class defines utility functions that generate filter closures used to filter posts
    based on certain conditions.
    """

    def __init__(self) -> None:
        self.filters: list[Callable[[PostMetadata], bool]] = []

    def add_filter(self, filter: Callable[[PostMetadata], bool]):
        self.filters.append(filter)

    def apply_filters(self, data: PostMetadata) -> bool:
        for f in self.filters:
            if not f(data):
                return False
        return True

    @staticmethod
    def generate_post_id_filter(post_id: str):
        def filter(data: PostMetadata) -> bool:
            return data.post_id == post_id
        return filter

    @staticmethod
    def generate_post_id_list_filter(post_id_list: list[str]):
        def filter(data: PostMetadata) -> bool:
            return data.post_id in post_id_list
        return filter

    @staticmethod
    def generate_catagory_filter(catagory: str):
        def filter(data: PostMetadata) -> bool:
            return data.catagory == catagory
        return filter

    @staticmethod
    def generate_tag_filter(tag: str):
        def filter(data: PostMetadata) -> bool:
            return tag in data.tags
        return filter

    @staticmethod
    def generate_tags_filter(tags: list[str]):
        def filter(data: PostMetadata) -> bool:
            # all required tags are present in post tags
            r = True
            for tag in tags:
                if tag not in data.tags:
                    r = False
                    break
            return r
        return filter

    @staticmethod
    def generate_after_timestamp_filter(timestamp: float):
        def filter(data: PostMetadata) -> bool:
            return data.created_timestamp > timestamp
        return filter

    @staticmethod
    def generate_before_timestamp_filter(timestamp: float):
        def filter(data: PostMetadata) -> bool:
            return data.created_timestamp < timestamp
        return filter


class Lablog:
    def __init__(self) -> None:
        self.posts: dict[str, PostMetadata] = dict()
        self.comments: dict[str, CommentData] = dict()

    def add_post(self, title: str, abstract: str, link: str, created_timestamp: Optional[float] = None, catagory: Optional[str] = None, tags: Optional[list[str]] = None) -> str:
        post_id = uuid.uuid4().__str__()
        post = PostMetadata(
            title=title,
            abstract=abstract,
            link=link,
            created_timestamp=created_timestamp if created_timestamp is not None else time.time(),
            catagory=catagory if catagory is not None else "Miscellaneous",
            tags=tags if tags is not None else list(),
            comments=[],
            post_id=post_id
        )
        self.posts[post_id] = post
        return post_id

    def modify_post(self, post_id: str, title: Optional[str] = None, abstract: Optional[str] = None, link: Optional[str] = None, created_timestamp: Optional[float] = None, catagory: Optional[str] = None, tags: Optional[list[str]] = None):
        if title is not None:
            self.posts[post_id].title = title
        if abstract is not None:
            self.posts[post_id].abstract = abstract
        if link is not None:
            self.posts[post_id].link = link
        if created_timestamp is not None:
            self.posts[post_id].created_timestamp = created_timestamp
        if catagory is not None:
            self.posts[post_id].catagory = catagory
        if tags is not None:
            self.posts[post_id].tags = tags

    def get_management_data(self) -> BlogData:
        # return all data for management
        return BlogData(posts=self.posts, comments=self.comments)

    def get_posts(
            self, post_id: Optional[str] = None,
            post_id_list: Optional[list[str]] = None,
            catagory: Optional[str] = None,
            tag: Optional[str] = None,
            tags: Optional[list[str]] = None,
            timestamp_start: Optional[float] = None,
            timestamp_stop: Optional[float] = None) -> PostsCollection:
        # constuct custom filter based on conditions given
        pf = PostFilter()
        if post_id is not None:
            pf.add_filter(
                PostFilter.generate_post_id_filter(post_id))
        if post_id_list is not None and len(post_id_list) > 0:
            pf.add_filter(
                PostFilter.generate_post_id_list_filter(post_id_list))
        if catagory is not None:
            pf.add_filter(
                PostFilter.generate_catagory_filter(catagory))
        if tag is not None:
            pf.add_filter(PostFilter.generate_tag_filter(tag))
        if tags is not None and len(tags) > 0:
            pf.add_filter(PostFilter.generate_tags_filter(tags))
        if timestamp_start is not None:
            pf.add_filter(
                PostFilter.generate_after_timestamp_filter(timestamp_start))
        if timestamp_stop is not None:
            pf.add_filter(
                PostFilter.generate_before_timestamp_filter(timestamp_stop))
        # apply filter for each post
        c = PostsCollection(posts=[])
        for post in self.posts.values():
            if pf.apply_filters(post):
                c.posts.append(post)
        # sort posts by descending time order
        c.posts.sort(key=lambda x: x.created_timestamp, reverse=True)
        return c

    def add_comment(self, name: str, content: str, contact_address: str, post_id: str, created_timestamp: Optional[float] = None, ip_address: Optional[str] = None, display: bool = True) -> str:
        if post_id not in self.posts:
            raise ValueError("post_id is not in current database.")
        comment_id = uuid.uuid4().__str__()
        comment = CommentData(
            name=name,
            content=content,
            contact_address=contact_address,
            created_timestamp=created_timestamp if created_timestamp is not None else time.time(),
            ip_address=ip_address if ip_address is not None else "No IP info",
            comment_id=comment_id,
            post_id=post_id,
            display=display
        )
        self.comments[comment_id] = comment
        # also add comment_id to post data
        self.posts[post_id].comments.append(comment_id)
        return comment_id

    def modify_comment(self, comment_id, name: Optional[str] = None, content: Optional[str] = None, contact_address: Optional[str] = None, created_timestamp: Optional[float] = None, ip_address: Optional[str] = None, post_id: Optional[str] = None, display: Optional[bool] = None):
        if name is not None:
            self.comments[comment_id].name = name
        if content is not None:
            self.comments[comment_id].content = content
        if contact_address is not None:
            self.comments[comment_id].contact_address = contact_address
        if created_timestamp is not None:
            self.comments[comment_id].created_timestamp = created_timestamp
        if ip_address is not None:
            self.comments[comment_id].ip_address = ip_address
        if post_id is not None:
            self.comments[comment_id].post_id = post_id
        if display is not None:
            self.comments[comment_id].display = display

    def get_comments(self, comment_id_list: list[str]) -> CommentsCollection:
        """
        NOTE: This method is for management, not for general users to view comments.
        It returns sensitive information of the users.
        """
        c = CommentsCollection(comments=[])
        for comment_id in comment_id_list:
            if comment_id in self.comments:
                c.comments.append(self.comments[comment_id])
        # sort comments by ascending time order
        c.comments.sort(key=lambda x: x.created_timestamp, reverse=False)
        return c

    def get_comments_for_display(self, comment_id_list: list[str]) -> DisplayCommentsCollection:
        """
        Returns a collection of comments, specified by id list, used for users
        to view comments.
        Only returns display=True comments
        """
        c = DisplayCommentsCollection(comments=[])
        for comment_id in comment_id_list:
            if comment_id in self.comments and self.comments[comment_id].display:
                comment = DisplayCommentData(
                    name=self.comments[comment_id].name,
                    content=self.comments[comment_id].content,
                    created_timestamp=int(self.comments[comment_id].created_timestamp)
                )
                c.comments.append(comment)
        # sort comments by ascending time order
        c.comments.sort(key=lambda x: x.created_timestamp, reverse=False)
        return c

    def delete_comment(self, comment_id: str):
        # remove comment and remove comment_id from post metadata
        if comment_id in self.comments:
            post_id = self.comments[comment_id].post_id
            self.posts[post_id].comments.remove(comment_id)
            del self.comments[comment_id]

    def serialize(self) -> str:
        data_obj = BlogData(
            posts=self.posts, comments=self.comments)
        return data_obj.model_dump_json(indent=2, exclude_none=True)

    def serialize_to_file(self, path: str):
        """
        Dump all blog data in memory to a file for backup or storage. 
        """
        with open(path, 'wb') as f:
            f.write(self.serialize().encode("utf-8"))

    def load(self, data: BlogData):
        self.posts = data.posts
        self.comments = data.comments

    def load_from_file(self, path: str):
        with open(path, 'rb') as f:
            r = f.read().decode("utf-8")
            r = json.loads(r)
        data = BlogData(**r)
        return self.load(data)

    def get_data_hash(self):
        f_content = self.serialize().encode("utf-8")
        data_hash = hashlib.sha256(f_content).hexdigest()
        return data_hash
