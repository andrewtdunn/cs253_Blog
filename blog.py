import os
import re
import random
import hashlib
import hmac
from string import letters

import webapp2
import jinja2

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                               autoescape=True)


secret = "donuts"


def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)


def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())


def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
          'Set-Cookie',
          '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))


def render_post(response, post):
    response.out.write('<b>' + post.subject + '</b><br>')
    response.out.write(post.content)


class MainPage(BlogHandler):
    def get(self):
        self.render("main.html")


def make_salt(length=5):
    return ''.join(random.choice(letters) for x in xrange(length))


def make_pw_hash(name, pw, salt=None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name+pw+salt).hexdigest()
    return '%s,%s' % (salt, h)


def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)


def users_key(group='default'):
    return db.Key.from_path('users', group)


class User(db.Model):
    name = db.StringProperty(required=True)
    pw_hash = db.StringProperty(required=True)
    email = db.StringProperty()

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, users_key())

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw, email=None):
        pw_hash = make_pw_hash(name, pw)
        return User(parent=users_key(),
                    name=name,
                    pw_hash=pw_hash,
                    email=email)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u


def blog_key(name='default'):
    return db.Key.from_path('blogs', name)


class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    user_id = db.StringProperty()
    likes = db.IntegerProperty(default=0)

    def render(self, curr_user_id=""):
        self._render_text = self.content.replace('\n', '<br/>')
        self.ref_id = self.key().id()
        editable = (curr_user_id == self.user_id)
        author = User.by_id(int(self.user_id)).name
        comment_number = Comment.count_by_post_id(self.ref_id)
        self.likes = Like.count_by_post_id(self.ref_id)
        isLiked = False
        loggedIn = True
        if curr_user_id:
            curr_user = User.by_id(int(curr_user_id))
            isLiked = Like.by_post_id_and_user_id(str(self.key().id()),
                                                  str(curr_user.key()
                                                  .id())).count()
        else:
            loggedIn = False
        return render_str("post.html", p=self, author=author,
                          editable=editable,
                          comment_number=comment_number,
                          isLiked=isLiked, loggedIn=loggedIn)


class Like(db.Model):
    post_id = db.StringProperty(required=True)
    user_id = db.StringProperty()

    @classmethod
    def count_by_post_id(cls, post_id):
        count = Like.all().filter('post_id =', str(post_id)).count()
        return count

    @classmethod
    def by_post_id_and_user_id(cls, post_id, user_id):
        like = Like.all().filter('post_id =', post_id)
        like = like.filter('user_id =', user_id)
        return like


class Comment(db.Model):
    post_id = db.StringProperty(required=True)
    content = db.StringProperty(required=True)
    user_id = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)\


    @classmethod
    def by_id(cls, comment_id):
        key = db.Key.from_path('Comment', int(comment_id))
        return db.get(key)

    @classmethod
    def by_post_id(cls, post_id):
        comments = Comment.all()
        comments = comments.filter('post_id =', str(post_id)).order('-created')
        return comments

    @classmethod
    def count_by_post_id(cls, post_id):
        count = Comment.all().filter('post_id =', str(post_id)).count()
        return count

    def render(self, curr_user_id=""):
        author = User.by_id(int(self.user_id))
        author_name = author.name
        editable = (str(self.user_id) == str(curr_user_id))
        return render_str("comment.html",
                          comment=self,
                          author_name=author_name,
                          editable=editable)


class BlogFront(BlogHandler):
    def get(self):
        posts = Post.all().order('-created')
        curr_user = self.read_secure_cookie("user_id")
        self.render('front.html', posts=posts, curr_user=curr_user)


class PostPage(BlogHandler):
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)
        curr_user_id = self.read_secure_cookie("user_id")
        if not post:
            self.error(404)
            return
        comments = Comment.by_post_id(post_id)

        self.render("permalink.html", post=post,
                    curr_user_id=curr_user_id,
                    comments=comments,
                    post_id=post_id)

    def post(self, post_id):
        if not self.user:
            self.redirect('/blog')
        # create new comment
        comment = self.request.get('comment')
        curr_user = self.read_secure_cookie("user_id")
        c = Comment(post_id=post_id, content=comment, user_id=curr_user)
        c.put()
        self.redirect("/blog/"+post_id)


class MakePost(BlogHandler):
    def get(self):
        if self.user:
            self.render("makepost.html")
        else:
            self.redirect('/blog')

    def post(self):
        if not self.user:
            self.redirect('/blog')

        subject = self.request.get('subject')
        content = self.request.get('content')
        post_id = self.request.get('post_id')

        if subject and content:
            # if there is a post_id, update existing post.
            # else create a new post
            user_id = self.user.key().id()
            if post_id:
                key = db.Key.from_path('Post', int(post_id), parent=blog_key())
                p = db.get(key)
                p.subject = subject
                p.content = content
                if (str(p.user_id) != str(self.user.key().id())):
                    self.redirect("/blog")
            else:
                p = Post(parent=blog_key(), subject=subject, content=content)
            p.user_id = str(user_id)
            p.put()
            self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "subject and content, please!"
            self.render("makepost.html",
                        subject=subject,
                        content=content,
                        error=error)


class EditPost(BlogHandler):
    def get(self, post_id):
        if self.user:
            key = db.Key.from_path('Post', int(post_id), parent=blog_key())
            post = db.get(key)

            if not post:
                self.error(404)
                return

            if (str(post.user_id) != str(self.user.key().id())):
                self.redirect("/blog")

            self.render("makepost.html",
                        subject=post.subject,
                        content=post.content,
                        post_id=post_id)
        else:
            self.redirect("/blog")


class DeletePost(BlogHandler):
    def get(self, post_id):
        if self.user:
            key = db.Key.from_path('Post', int(post_id), parent=blog_key())
            post = db.get(key)

            if not post:
                self.error(404)
                return

            if (str(post.user_id) == str(self.user.key().id())):
                post.delete()
            self.redirect("/blog")
        else:
            self.redirect("/login")


class EditComment(BlogHandler):
    def get(self, comment_id):
        if self.user:
            comment = Comment.by_id(comment_id)
            if (str(comment.user_id) == str(self.user.key().id())):
                self.render("comment-form.html", comment=comment)
            else:
                self.redirect("/blog/" + comment.post_id)
        else:
            self.redirect("/blog/" + comment_id)

    def post(self, comment_id):
        if self.user:
            comment = Comment.by_id(comment_id)
            if (str(comment.user_id) == str(self.user.key().id())):
                comment.content = self.request.get("comment")
                comment.put()
            self.redirect("/blog/" + comment.post_id)
        else:
            self.redirect("'/blog")


class DeleteComment(BlogHandler):
    def get(self, comment_id):
        if self.user:
            comment = Comment.by_id(int(comment_id))
            if (str(comment.user_id) == str(self.user.key().id())):
                comment.delete()
            self.redirect("/blog/" + comment.post_id)
        else:
            self.redirect("/blog")


class NewLike(BlogHandler):
    def get(self, post_id):
        if self.user:
            user_id = str(self.user.key().id())
            l = Like(post_id=str(post_id), user_id=str(user_id))
            l.put()
            self.redirect("/blog")
        else:
            self.redirect("/blog")


class UnLike(BlogHandler):
    def get(self, post_id):
        if self.user:
            user_id = str(self.user.key().id())
            l = Like.by_post_id_and_user_id(post_id=str(post_id),
                                            user_id=str(user_id))
            l.get().delete()
            self.redirect("/blog")
        else:
            self.redirect("/blog")

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PASS_RE = re.compile(r"^.{3,20}$")
EMAIL_RE = re.compile(r"^[\S]+@[\S]+\.[\S]+$")


def valid_username(username):
    return username and USER_RE.match(username)


def valid_password(password):
    return password and PASS_RE.match(password)


def valid_email(email):
    return not email or EMAIL_RE.match(email)


class Signup(BlogHandler):
    def get(self):
        self.render("signup-form.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username=self.username,
                      email=self.email)

        if not valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True

        if not valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords don't match."
            have_error = True

        if not valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:
            self.done()

    def done(self, *a, **kw):
        raise NotImplementedError


class Register(Signup):
    def done(self):
        # make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signup-form.html',
                        username=self.username,
                        email=self.email,
                        error_username=msg)
        else:
            u = User.register(self.username, self.password, self.email)
            u.put()

            self.login(u)
            self.redirect('/blog')


class Login(BlogHandler):
    def get(self):
        self.render('login-form.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)
        if u:
            self.login(u)
            self.redirect('/blog')
        else:
            msg = 'Invalid login'
            self.render('login-form.html', error=msg)


class Logout(BlogHandler):
    def get(self):
        self.logout()
        self.redirect('/blog')


app = webapp2.WSGIApplication([('/', BlogFront),
                              ('/blog/?', BlogFront),
                              ('/blog/([0-9]+)', PostPage),
                              ('/newlike/([0-9]+)', NewLike),
                              ('/unlike/([0-9]+)', UnLike),
                              ('/blog/makepost', MakePost),
                              ('/post/edit/([0-9]+)', EditPost),
                              ('/post/delete/([0-9]+)', DeletePost),
                              ('/comment/edit/([0-9]+)', EditComment),
                              ('/comment/delete/([0-9]+)', DeleteComment),
                              ('/signup', Register),
                              ('/login', Login),
                              ('/logout', Logout)],
                              debug=True)