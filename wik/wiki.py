import webapp2
import jinja2
import os
import re
import cgi
import hmac
import random
import json
import datetime
import time
import logging
from collections import namedtuple
from google.appengine.ext import db
from google.appengine.api import memcache

import login
import base_handler

PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'


class WikiPage(db.Model):
	name = db.StringProperty(required=True)
	history = db.TextProperty(required=True)
	
	@classmethod
	def get_page(cls, page_name):
		q = WikiPage.all()
		q.filter("name =", page_name)
		q = q.fetch(limit=1)
		return q[0] if len(q) == 1 else None

class RedirectHome(webapp2.RequestHandler):
	def get(self):
		self.redirect('/home')

class WikiRequestHandler(login.CookieUserRequestHandler):
    def get(self, page_name="/"):
		template_vars = {}
		user = self.get_user_from_cookie()
		template_vars["username"] = user.name if user else ""
		template_vars["page_name"] = page_name
		page = WikiPage.get_page(page_name)
		if page:
			history = json.loads(page.history)
			version = self.request.get("v")
			version = get_version_from_user_request(version, len(history))
			template_vars["content"] = json.loads(page.history)[version-1][1]
			self.write("Wiki.html", **template_vars)
		elif page_name == "/home":	
			# create the home page if it is not existing
			# it can serve as a model for other pages
			content = "Welcome home"
			page = WikiPage(name=page_name, \
							history=json.dumps([(time.strftime("%c"), content)]))
			page.put()
			template_vars["content"] = content
			self.write("Wiki.html", **template_vars)
		else:
			self.redirect('/_edit%s' % page_name)

def get_version_from_user_request(param, max_version):
	version = int(param) if param.isdigit() else max_version
	if not (version > 0 and version <= max_version):
		version = max_version
	return version

class EditWikiRequestHandler(login.CookieUserRequestHandler):
	def get(self, page_name):
		user = self.get_user_from_cookie()
		template_vars = {}
		template_vars["username"] = user.name if user else ""
		template_vars["page_name"] = page_name
		if user:
			page = WikiPage.get_page(page_name)
			if page:
				history = json.loads(page.history)
				version = self.request.get("v")
				version = get_version_from_user_request(version, len(history))
				template_vars["version"] = version
				content = json.loads(page.history)[version-1][1]
			else:
				content = ""
			template_vars["content"] = content
			self.write("EditWiki.html", **template_vars)
		else:
			self.error(404)
			
	def post(self, page_name):
		user = self.get_user_from_cookie()
		template_vars = {}
		template_vars["username"] = user.name if user else ""
		template_vars["page_name"] = page_name
		if user:
			content = self.request.get("content")
			template_vars["content"] = content
			page = WikiPage.get_page(page_name)
			if content:
				history = []
				if not page:
					page = WikiPage(name=page_name, history=json.dumps(history))
				else:
					history = json.loads(page.history)
				version = self.request.get("v")
				if version:
					version = get_version_from_user_request(version, \
															len(history)+1)
				else:
					version = len(history)+1
				self.add_content_to_history(history, version, content)
				page.history = json.dumps(history)
				# danger ici faire de l'escape html
				page.put()
				self.redirect(page_name)
			else:
				template_vars["error"] = "You cannot add a blank page"
				self.write("EditWiki.html", **template_vars)
	
	def add_content_to_history(self, history, version, content):
		if len(history) == 0:
			history.append((time.strftime("%c"), content))
		elif version > len(history):
			if not history[-1][1] == content:
				history.append((time.strftime("%c"), content))
		else:
			if not history[version-1][1] == content:
				history[version-1] = ((time.strftime("%c"), content))

class HistoryRequestHandler(login.CookieUserRequestHandler):
	def get(self, page_name):
		user = self.get_user_from_cookie()
		template_vars = {}
		template_vars["username"] = user.name if user else ""
		template_vars["page_name"] = page_name
		template_vars["view"] = "history"
		page = WikiPage.get_page(page_name)
		if page:
			history = json.loads(page.history)
			template_vars["history"] = self.limit_content_size(history)
			self.write("History.html", **template_vars)
		else:
			self.error(404)
	
	def limit_content_size(self, history):
		return map(lambda x: [x[0], self.cut_string(x[1], 60)], history)
	
	def cut_string(self, string, max_length):
		if len(string) <= max_length:
			return string
		else:
			return string[:max_length]+"..."

app = webapp2.WSGIApplication([('/', RedirectHome), \
							   ('/signup', login.SignUp), \
							   ('/login', login.Login), \
							   ('/logout', login.Logout), \
							   ('/_edit' + PAGE_RE, EditWikiRequestHandler), \
							   ('/_history' + PAGE_RE, HistoryRequestHandler), \
							   (PAGE_RE, WikiRequestHandler)], \
							   debug=True)