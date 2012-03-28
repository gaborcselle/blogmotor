#!/usr/bin/env python
#
# Blog Motor - The Engine that Powers Your Blog on Google App Engine
# Sample main.py File
#
# Go to: http://code.google.com/p/blog-motor
# Creator: Gabor Cselle, www.gaborcselle.com, 9/22/2009
# Contributors: <YOUR NAME HERE>
# Some code copied from Bret Taylor, http://bret.appspot.com/
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

import cgi
import os
import re
import functools
import datetime
import logging

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.ext.webapp import template

#######################################################
# Models

class BlogMotorSettings(db.Model):
  """Global settings for BlogMotor blog"""
  blogUrl = db.StringProperty(required=True, default="http://www.yourdomain.com/blog/")
  blogTitle = db.StringProperty(required=True, default="Your Blog's Title")
  blogSubtitle = db.StringProperty(required=True, default="A Snazzy Tagline for Your Blog")
  
  authorName = db.StringProperty(required=True, default="BlogMotor")
  authorUrl = db.StringProperty(required=True, default="http://www.gaborcselle.com/")
  
  postsPerPage = db.IntegerProperty(required=True, default=10)
  
  disqusEnabled = db.BooleanProperty(required=True, default=False)
  disqusBlogID = db.StringProperty() # disqus blog id
  
  created = db.DateTimeProperty(auto_now_add=True)
  updated = db.DateTimeProperty(auto_now=True)
  
def get_settings():
  """Get the settings singleton.
  TODO(gabor): Use a proper python Singleton pattern
  """
  y = BlogMotorSettings.all().get()
  
  if y is not None:
    return y
  
  y = BlogMotorSettings()
  y.put()
  return y

class BlogMotorPost(db.Model):
  """One post in the blog."""
  title = db.StringProperty(required=True)
  body = db.TextProperty(required=True)
  authorName = db.StringProperty(required=True)
  authorUrl = db.StringProperty()
  
  published = db.DateTimeProperty(auto_now_add=True)
  updated = db.DateTimeProperty(auto_now=True)
  
  isDraft = db.BooleanProperty() # True if Blog Post is only saved, not published

#######################################################
# Utils
  
def administrator(method):
  """Administrator wrapper, copied from Bret Taylor:
  http://bret.appspot.com/entry/experimenting-google-app-engine
  """
  
  @functools.wraps(method)
  def wrapper(self, *args, **kwargs):
      user = users.get_current_user()
      if not user:
          if self.request.method == "GET":
              self.redirect(users.create_login_url(self.request.uri))
              return
          raise web.HTTPError(403)
      elif not users.is_current_user_admin():
          raise web.HTTPError(403)
      else:
          return method(self, *args, **kwargs)
  return wrapper

#######################################################
# Blog Motor Views

class BlogRedirect(webapp.RequestHandler):
  """Redirects /blog -> /blog/
  TODO(gabor): is there a cleaner way to do this via the webapp config?"""
  def head(self, *args):
    return self.get(*args)

  def get(self):
    self.redirect("/blog/")

class Blog(webapp.RequestHandler):
  """Main blog page with list of entries"""
  def head(self, *args):
    return self.get(*args)

  def get(self):
    blog_settings = get_settings()
  
    entries = BlogMotorPost.all().order('-published').fetch(blog_settings.postsPerPage)
    
    path = os.path.join(os.path.dirname(__file__), 'blog_template.html')
    self.response.out.write(template.render(path, {"entries" : entries,
      "post_page" : False,
      "blog_settings" : blog_settings}))
    
class BlogPost(webapp.RequestHandler):
  """View for one specific blog post."""
  def head(self, *args):
    return self.get(*args)
    
  def get(self, id):
    entry = BlogMotorPost.get_by_id(int(id))
    
    blog_settings = BlogMotorSettings.all().get()
    
    path = os.path.join(os.path.dirname(__file__), 'blog_template.html')
    self.response.out.write(template.render(path, {"entries" : [entry],
      "post_page" : True, "blog_settings" : blog_settings}))
    
class BlogAtomXml(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)

  def get(self):
    blog_settings = get_settings()
  
    entries = BlogMotorPost.all().order('-published')
    last_update = BlogMotorPost.all().order('-updated').get()
    blog_updated = last_update.updated if last_update else datetime.datetime.min
    
    path = os.path.join(os.path.dirname(__file__), 'blog_atom_template.xml')
    self.response.headers['Content-Type'] = "application/atom+xml"
    self.response.out.write(template.render(path, {"entries" : entries,
      "blog_updated" : blog_updated,
      "blog_settings" : blog_settings
      }))

class AdminBlog(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)
  
  @administrator
  def get(self):
    posts = BlogMotorPost.all().order('-published')
    
    path = os.path.join(os.path.dirname(__file__), 'admin_blog_list.html')
    self.response.out.write(template.render(path, {'posts' : posts}))
 
class AdminBlogEdit(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)
  
  @administrator
  def get(self, id):
    y = BlogMotorPost.get_by_id(int(id))
    
    if not y:
      self.error(404)
      self.response.out.write('<html><title>404 - Page Not Found</title><body>404 - page not found</body></html>')
      return
    
    path = os.path.join(os.path.dirname(__file__), 'admin_blog_edit.html')
    self.response.out.write(template.render(path, {'y' : y}))
  
  @administrator
  def post(self):
    id = int(self.request.get('id'))
    
    title = self.request.get('title')
    body = self.request.get('body')
    authorName = self.request.get('authorName')
    authorUrl = self.request.get('authorUrl')
    
    y = models.BlogPost.get_by_id(id)
    y.title = title
    y.body = body
    y.authorName = authorName
    y.authorUrl = authorUrl
    y.put()
    
    self.redirect("/blog/posts/%i" % id)
    return
 

class AdminBlogSettings(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)
  
  @administrator
  def get(self):
    y = get_settings()
    
    path = os.path.join(os.path.dirname(__file__), 'admin_blog_settings.html')
    self.response.out.write(template.render(path, {'settings' : y}))
  
  @administrator
  def post(self):
    #TODO(gabor): Save settings
    return
 
   
class AdminBlogNew(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)
  
  @administrator
  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'admin_blog_new.html')
    self.response.out.write(template.render(path, {}))
  
  @administrator
  def post(self):
    title = self.request.get('title')
    body = self.request.get('body')
    authorName = self.request.get('authorName')
    authorUrl = self.request.get('authorUrl')    
    
    y = BlogMotorPost(title=title, body=body, authorName=authorName, authorUrl=authorUrl)
    y.put()
    
    self.redirect("/blog/posts/%s" % y.key().id())

class NotFoundPageHandler(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)

  def get(self):
    self.error(404)
    self.response.out.write('<html><title>404 - Page Not Found</title><body>404 - page not found</body></html>')
    
class BlogPostRedirect(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)

  def get(self, id):
    self.redirect("/blog/posts/%s" % id)

class BlogRedirect(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)

  def get(self):
    self.redirect("/blog/")
    
class NotFoundPageHandler(webapp.RequestHandler):
  def head(self, *args):
    return self.get(*args)

  def get(self):
    self.error(404)
    self.response.out.write('<html><title>404 - Page Not Found</title><body>404 - page not found</body></html>')

application = webapp.WSGIApplication([
  ('/blog', BlogRedirect),
  ('/blog/', Blog),
  (r'/blog/posts/([0-9]+)', BlogPost),
  (r'/blog/posts/([0-9]+)/', BlogPostRedirect),
  ('/blog/atom.xml', BlogAtomXml),
  ('/admin/blog/', AdminBlog),
  ('/admin/blog/settings/', AdminBlogSettings),
  ('/admin/blog/new/', AdminBlogNew),
  (r'/admin/blog/edit/([0-9]+)', AdminBlogEdit),
  (r'^.*$', NotFoundPageHandler),
  ], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()