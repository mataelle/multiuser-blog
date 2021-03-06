#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
from google.appengine.ext import db
import time

from settings import templates_dir, jinja_env, render_str
from models import User, Post, Like, Comment

from utils import (
    make_secure_val, check_secure_val,
    make_salt, make_pw_hash, valid_pw, secret)


###### blog handlers
class Handler(webapp2.RequestHandler):
    '''
        Basic handler class.
        When initialising, reads cookie and sets
        current user (if exists) in the field named user.
        Provides method for rendering templates and methods
        for user's authorization

        initialize - is called when the instance of class is created
        render_str - render given template with given params
        render - write rendered template in response object
        set_cookie - sets cookie
        read_cookie - reads cookie
        set_user - set cookie for user and remember user
            in the field of current instance
            (is used when user is logging in)
        unset user - used when user logs out, erasing cookie and
            clearing field user.
    '''
    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        username = self.read_cookie('username')
        if username and len(username) == 0:
            username = None
        self.user = username and User.get_by_username(username)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        params['user'] = self.user if self.user else None
        return t.render(params)

    def render(self, template, **kw):
        self.response.write(self.render_str(template, **kw))

    def set_cookie(self, name, value):
        secure_val = make_secure_val(value)
        self.response.headers.add_header(
            'Set-Cookie', '%s=%s; Path=/' % (name, secure_val))

    def read_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def set_user(self, user):
        self.user=user
        self.set_cookie('username', str(user.username))

    def unset_user(self):
        self.user=None
        self.set_cookie('username', '')


class BlogFront(Handler):
    '''
        Handler for front page.
        Renders page with 10 recent posts.
    '''
    def get(self):
        posts = Post.all().order('-created')[:10]
        self.render('blog.html', posts=posts)


class PostHandler(Handler):
    '''
        Base handler for pages dealing with posts.

        get_post - get post by key if exists
        check_post_author - check if current user
            is the author of the given post
    '''
    def get_post(self, key):
        post = db.get(key)
        if post:
            return post
        self.render('page_not_found.html')

    def check_post_author(self, post):
        if not post.author or not self.user or \
            post.author.username != self.user.username:
            self.render('page_not_allowed.html')
            return False
        return True



class PostPage(PostHandler):
    '''Handler for separate post page'''
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if not post:
            return

        self.render('post_permalink.html', post=post)


class EditPostPage(PostHandler):
    ''' Edit post page handler'''
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if not post or not self.check_post_author(post):
            return

        self.render('post_edit.html',
                    subject=post.subject,
                    content=post.content)

    def post(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if not post or not self.check_post_author(post):
            return

        subject = self.request.get('subject')
        content = self.request.get('content')
        if subject and content:
            post.subject = subject
            post.content = content
            post.put()
            self.redirect('/blog/'+str(post.key().id()))
        else:
            self.render('post_edit.html',
                        subject=subject,
                        content=content,
                        err_msg=True)


class DeletePostPage(PostHandler):
    '''
    Delete post page handler.
    Renders page where user confirms his intention
    to delete post. Delets post, if confirmed.
    '''

    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if not post or not self.check_post_author(post):
            return

        self.render('post_delete.html', post=post)

    def post(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if not post or not self.check_post_author(post):
            return

        for comment in post.comment_set:
            comment.delete()
        post.delete()
        time.sleep(1)
        self.redirect('/blog', permanent=True)


class NewPost(PostHandler):
    '''Handler for new post form page'''
    def get(self):
        if not self.user:
            self.redirect('/login')

        self.render('newpost.html')

    def post(self):
        if not self.user:
            return self.redirect('/login')

        subject = self.request.get('subject')
        content = self.request.get('content')
        if subject and content:
            post = Post(subject=subject,
                        content=content,
                        author=self.user)
            post.put()
            self.redirect('/blog/'+str(post.key().id()))
        else:
            self.render('newpost.html', content=content,
                        subject=subject, err_msg=True)

import json
class LikePost(PostHandler):
    '''
        Handler processing post ajax query - like post.
        post_id - given as a parameter in url
        user is known from cookie read by base class Handler.
    '''
    def post(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)

        # check that
        #   post exists,
        #   user is not liking his own post,
        #   user didn't like this post
        if post and self.user.username != post.author.username and\
            not post.liked(self.user):
            like = Like(user = self.user, post = post)
            like.put()
            self.response.out.write(json.dumps({}))

class CommentPost(PostHandler):
    '''
        Handler processing post ajax query - comment on post.
        post_id - given as a parameter in url
        user is known from cookie read by base class Handler.
        comment - is received as an ajax request data
    '''

    def post(self, post_id):
        comment_text = self.request.get('comment')
        #comments can't be empty
        if not comment_text:
            self.response.out.write(json.dumps({'err_msg': True}))
            return

        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        comment = Comment(user = self.user,
                          post = post,
                          comment = comment_text)
        comment.put()
        self.response.out.write(comment.render(self.user))

class CommentDelete(Handler):
    '''
        Handler processing post ajax query - delete comment.
        comment_id - given as a parameter in url
        user is known from cookie read by base class Handler.
    '''

    def post(self, comment_id):
        comment = Comment.get_by_id(int(comment_id))
        # check that comment exists and it's author is current user
        if not comment or \
            comment.user.key().id() != self.user.key().id():
            self.response.out.write(json.dumps({'err_msg_critical': True}))
            return
        comment.delete()
        self.response.out.write(json.dumps({}))

class CommentEdit(Handler):
    '''
        Handler processing post ajax query - edit comment.
        comment_id - given as a parameter in url
        user is known from cookie read by base class Handler.
        comment - is received as an ajax request data
    '''

    def post(self, comment_id):
        comment = Comment.get_by_id(int(comment_id))
        # check that comment exists and it's author is current user
        if not comment or \
            comment.user.key().id() != self.user.key().id():
            self.response.out.write(json.dumps({'err_msg_critical': True}))
            return

        comment_text = self.request.get('comment')
        # comment can't be empty
        if not comment_text or len(comment_text) == 0:
            self.response.out.write(json.dumps(({'err_msg': True})))
            return

        comment.comment = comment_text
        comment.put()
        self.response.out.write(comment.render(self.user))


###### username, email, password validators
import re

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    if username is not None:
        return USER_RE.match(username) is not None
    return False

EMAIL_RE = re.compile(r"^[\S]+@[\S]+.[\S]+$")
def valid_email(email):
    if email is not None and len(email) > 0:
        return EMAIL_RE.match(email) is not None
    return True

PASSWORD_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    if password is not None:
        return PASSWORD_RE.match(password) is not None
    return False

def match_password(password, verify):
    return password == verify


###### handlers for user stuff
class SignUpHandler(Handler):
    '''
        Handler for sign up form
    '''
    def get(self):
        self.render('signup.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        err_username = not valid_username(username)
        err_password = not valid_password(password)
        err_email = not valid_email(email)
        err_verify = not match_password(password, verify) \
            if err_password is False else False

        # render form with errors if any
        if err_username or err_password or err_verify or err_email:
            self.render('signup.html',
                        username=username,
                        email=email,
                        err_username=err_username,
                        err_password=err_password,
                        err_verify=err_verify,
                        err_email=err_email)

        else:
            # render form with error if user exists
            if db.GqlQuery('select * from User where username=:1',
                            username).count() > 0:
                self.render('signup.html',
                            username=username,
                            email=email,
                            err_username_taken=True)
            else:
                user = User.register(username=username,
                                    password=password,
                                    email=email)
                self.set_user(user)
                user.put()
                self.render('page_welcome.html')


class LoginHandler(Handler):
    '''
        Handler for login form
    '''
    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        # check that user exists and data provided is correct
        user = User.login(username, password)
        if user is None:
            self.render('login.html', error=True)
            return

        self.set_user(user)
        self.redirect('/blog', permanent=True)


class LogoutHandler(Handler):
    '''
        Handler for logout
    '''
    def get(self):
        self.unset_user()
        self.redirect('/login')

app = webapp2.WSGIApplication([
    ('/', BlogFront),
    ('/blog/?', BlogFront),
    ('/blog/([0-9]+)', PostPage),
    ('/blog/([0-9]+)/delete', DeletePostPage),
    ('/blog/([0-9]+)/edit', EditPostPage),
    ('/blog/([0-9]+)/like', LikePost),
    ('/blog/([0-9]+)/comment', CommentPost),
    ('/comment/([0-9]+)/delete', CommentDelete),
    ('/comment/([0-9]+)/edit', CommentEdit),
    ('/blog/newpost', NewPost),
    ('/signup', SignUpHandler),
    ('/login', LoginHandler),
    ('/logout', LogoutHandler),
], debug=True)
