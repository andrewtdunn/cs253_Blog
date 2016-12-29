import webapp2
from classes.models import *
from helpers.helpers import *


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


class MainPage(BlogHandler):
    def get(self):
        self.render("main.html")


class BlogFront(BlogHandler):
    def get(self):
        posts = Post.all().order('-created')
        curr_user = self.read_secure_cookie("user_id")
        self.render('front.html', posts=posts, curr_user=curr_user)


class PostPage(BlogHandler):
    def get(self, post_id):
        post = Post.by_id(post_id)
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
            self.redirect('/login')

    def post(self):
        if not self.user:
            return self.redirect('/login')

        subject = self.request.get('subject')
        content = self.request.get('content')
        post_id = self.request.get('post_id')

        if subject and content:
            # if there is a post_id, update existing post.
            # else create a new post
            user_id = self.user.key().id()
            if post_id:
                p = Post.by_id(post_id)
                if not p:
                    self.error(404)
                    return
                p.subject = subject
                p.content = content
                if (str(p.user_id) != str(self.user.key().id())):
                    return self.redirect("/blog")
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
            post = Post.by_id(post_id)

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
            post = Post.by_id(post_id)

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
            if not comment:
                self.error(404)
                return
            if (str(comment.user_id) == str(self.user.key().id())):
                self.render("comment-form.html", comment=comment)
            else:
                self.redirect("/blog/" + comment.post_id)
        else:
            self.redirect("/blog/" + comment_id)

    def post(self, comment_id):
        if self.user:
            comment = Comment.by_id(comment_id)
            if not comment:
                self.error(404)
                return
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
            if not comment:
                self.error(404)
                return
            if (str(comment.user_id) == str(self.user.key().id())):
                comment.delete()
            self.redirect("/blog/" + comment.post_id)
        else:
            self.redirect("/blog")


class NewLike(BlogHandler):
    def get(self, post_id):
        if self.user:
            user_id = str(self.user.key().id())
            p = Post.by_id(post_id)
            if not p:
                self.error(404)
                return
            if (str(p.user_id) == str(user_id)):
                return self.redirect("/login")
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
            if not l:
                self.error(404)
                return
            l.get().delete()
            self.redirect("/blog")
        else:
            self.redirect("/blog")


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