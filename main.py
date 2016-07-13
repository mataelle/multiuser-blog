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
import jinja2
import os
import random
import hmac
import hashlib

templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(templates_dir), autoescape=True)

###### functions providing cookie security
secret = "kinda very secret string"

def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val

###### functions providing password security
from string import letters
def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)

def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)

def users_key(group = 'default'):
    return db.Key.from_path('users', group)


###### database models
from google.appengine.ext import db

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class User(db.Model):
    username = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)
    email = db.StringProperty(required = False)

    @classmethod
    def get_by_username(cls, username):
        u = cls.all().filter('username =', str(username)).get()
        return u

    @classmethod
    def register(cls, username, password, email = None):
        pw_hash = make_pw_hash(username, password)
        return cls(username = username,
                    pw_hash = pw_hash,
                    email = email)

    @classmethod
    def login(cls, username, password):
        if username is None or password is None:
            return None
        user = cls.get_by_username(username)
        if user and valid_pw(username, password, user.pw_hash):
            return user
        return None

class Post(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)
    author = db.ReferenceProperty(User)

    # @classmethod
    # def comments(cls):
    #     db.GqlQuery('select * from Comment where post=:1 order by created desc', self)

    def render(self, user = None):
        return render_str("post.html", post = self, user = user)

class Like(db.Model):
    user = db.ReferenceProperty(User)
    post = db.ReferenceProperty(Post)
    created = db.DateTimeProperty(auto_now_add = True)

    @classmethod
    def like(cls, user, post):
        return cls(user = user, post = post)

class Comment(db.Model):
    user = db.ReferenceProperty(User)
    post = db.ReferenceProperty(Post)
    comment = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)



###### blog handlers
# basic handler class
class Handler(webapp2.RequestHandler):

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


# handler for front page
class BlogFront(Handler):

    def get(self):
        posts = Post.all().order('-created')[:10]
        self.render('blog.html', posts=posts)


# base handler for post-pages
class PostHandler(Handler):
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


# handler for post page
class PostPage(PostHandler):

    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if not post:
            return

        self.render('post_permalink.html', post=post)


# handler for edit post page
class EditPostPage(PostHandler):

    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if not post or not self.check_post_author(post):
            return

        self.render('post_edit.html', subject=post.subject, content=post.content)

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
            self.render('post_edit.html', subject=subject, content=content, err_msg=True)


# handler for delete post page
class DeletePostPage(PostHandler):

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

        post.delete()
        self.redirect('/blog')

# handler for new post form page
class NewPost(PostHandler):

    def get(self):
        if not self.user:
            self.redirect('/login')

        self.render('newpost.html')

    def post(self):
        if not self.user:
            self.redirect('/login')

        subject = self.request.get('subject')
        content = self.request.get('content')
        if subject and content:
            post = Post(subject=subject, content=content, author=self.user)
            post.put()
            self.redirect('/blog/'+str(post.key().id()))
        else:
            self.render('newpost.html', content=content,
                        subject=subject, err_msg=True)

import json
# like post page
class LikePost(PostHandler):

    def post(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = self.get_post(key)
        if post and self.user.username != post.author.username:
            post_like_set = Post.get_by_id(int(post_id)).like_set
            if all ([like.user.key().id() != self.user.key().id() for like in post_like_set]):
                like = Like(user = self.user, post = post)
                like.put()
                self.response.out.write(json.dumps(({})))

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
# handler for sign up form
class SignUpHandler(Handler):

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

        if err_username or err_password or err_verify or err_email:
            self.render('signup.html', username=username, email=email,
                        err_username=err_username, err_password=err_password,
                        err_verify=err_verify, err_email=err_email)
        else:
            if db.GqlQuery('select * from User where username=:1', username).count() > 0:
                self.render('signup.html', username=username, email=email,
                            err_username_taken=True)
            else:
                user = User.register(username=username, password=password, email=email)
                self.set_user(user)
                user.put()
                self.render('page_welcome.html')

# handler for login form
class LoginHandler(Handler):

    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        user = User.login(username, password)
        if user is None:
            self.render('login.html', error=True)
            return

        self.set_user(user)
        self.redirect('/blog', permanent=True)

# handler for logout
class LogoutHandler(Handler):

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
    ('/blog/newpost', NewPost),
    ('/signup', SignUpHandler),
    ('/login', LoginHandler),
    ('/logout', LogoutHandler),
], debug=True)
