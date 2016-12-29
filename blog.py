import webapp2

from helpers.helpers import *
from classes.models import *
from classes.handlers import *


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
