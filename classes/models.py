from google.appengine.ext import db
from helpers.helpers import *


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


class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    user_id = db.StringProperty()
    likes = db.IntegerProperty(default=0)

    @classmethod
    def by_id(cls, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        return db.get(key)

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
