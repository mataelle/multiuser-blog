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

templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(templates_dir), autoescape=True)

from google.appengine.ext import db


class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)


class User(db.Model):
    username = db.StringProperty(required=True)
    password = db.StringProperty(required=True)


# basic habdler class
class Handler(webapp2.RequestHandler):

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.response.write(self.render_str(template, **kw))

    def set_cookie(self, name, value):
        self.response.headers.add_header(
            'Set-Cookie', '%s=%s; Path=/' % (name, value))


# handler for front page
class BlogFront(Handler):

    def get(self):
        posts = Post.all().order('-created')[:10]
        self.render('blog.html', posts=posts)


# handler for post page
class PostPage(Handler):

    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id))
        post = db.get(key)

        if not post:
            self.error(404)
            return

        self.render('post.html', post=post)


# handler for new post form page
class NewPost(Handler):

    def get(self):
        self.render('newpost.html')

    def post(self):
        subject = self.request.get('subject')
        content = self.request.get('content')
        if subject and content:
            post = Post(subject=subject, content=content)
            post.put()
            self.redirect(str(post.key().id()))
        else:
            self.render('newpost.html', content=content,
                        subject=subject, err_msg=True)


# username, email, password validators
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
                user = User(username=username, password=password)
                user.put()
                self.set_cookie('username', str(username))
                self.redirect('/blog')

# handler for login form
class LoginHandler(Handler):

    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        if username is None or password is None:
            self.render('login.html', error=True)
            return
        user = db.GqlQuery('select * from User where username=:1', username)
        if user.count() == 0:
            self.render('login.html', error=True)
            return
        user = user.get()
        if user.password != password:
            self.render('login.html', error=True)
            return

        self.set_cookie('username', str(username))
        self.redirect('/blog')


# handler for logout
class LogoutHandler(Handler):

    def get(self):
        self.set_cookie('username', '')
        self.redirect('/signup')

app = webapp2.WSGIApplication([
    ('/', BlogFront),
    ('/blog/?', BlogFront),
    ('/blog/([0-9]+)', PostPage),
    ('/blog/newpost', NewPost),
    ('/signup', SignUpHandler),
    ('/login', LoginHandler),
    ('/logout', LogoutHandler),
], debug=True)
