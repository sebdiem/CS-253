import webapp2
import re
import string
import hmac
import random

from google.appengine.ext import db

import base_handler

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PWD_RE = re.compile(r"^.{3,20}$")
EMAIL_RE = re.compile(r"^[\S]+@[\S]+\.[\S]+$")
NONEMPTY_RE = re.compile(r"^(?!\s*$).+")

__SECRET = r"{2lzeLkjz,3M30JKE0k"

def valid_username(username):
	return USER_RE.match(username)

def valid_password(password):
	return PWD_RE.match(password)

def valid_email(email):
	return (email == "" or EMAIL_RE.match(email))

def valid_verify(password, verify):
	return password == verify

def valid_nonempty(any_string):
	return NONEMPTY_RE.match(any_string)
	
def format_date(date):
	return datetime.date.strftime(date,"%a %b %m %H:%M:%S %y")

class User(db.Model):
	name = db.StringProperty(required=True)
	password = db.StringProperty(required=True)
	email =  db.StringProperty()

def make_salt():
	return "".join([random.choice(string.letters) for x in xrange(20)])
	
def make_pwd_hash(password, salt = None):
	if not salt:
		salt = make_salt()
	## hmac default is md5 : this is not secure
	return "%s|%s" % (hmac.new(salt, password).hexdigest(), salt)

def verify_pwd(password, h):
	l = str.split(h,"|")
	if len(l) == 2:
		pwd_hash, salt = l
	return make_pwd_hash(password, salt) == pwd_hash

def create_cookie(user_id, salt):
	global __SECRET
	path = "Path=/"
	if user_id:
		hash = hmac.new(__SECRET, salt).hexdigest()
		return "user_id=%s|%s; %s" % (user_id, hash, path)
	else:
		return "user_id=;%s" % path

class AuthCookieCreator(base_handler.BaseRequestHandler):
	def writeAuthCookieAndRedirect(self, id, salt):
		cookie_string = create_cookie(id, salt)
		self.response.headers.add_header('Set-Cookie', cookie_string)
		self.redirect('/')

class SignUp(AuthCookieCreator):
	def get(self):
		self.write("Signup.html")
	
	def post(self):
		template_data = {}
		template_data["email"] = self.request.get('email')
		template_data["password"] = self.request.get('password')
		template_data["verify"] = self.request.get('verify')
		template_data["username"] = self.request.get('username')
		template_data["username_error"] = "Invalid username"
		template_data["password_error"] = "Invalid password"
		template_data["verify_error"] = "Verify does not match password"
		template_data["email_error"] = "Invalid email"
		if valid_username(template_data["username"]):
			template_data["username_error"] = ""
		if valid_password(template_data["password"]):
			template_data["password_error"] = ""
		if valid_verify(template_data["password"], template_data["verify"]):
			template_data["verify_error"] = ""
		if valid_email(template_data["email"]):
			template_data["email_error"] = ""
		error_filter = filter(lambda x : x[0][-5:]=="error", template_data.items())
		if ''.join([x[1] for x in error_filter]):
			self.write("Signup.html", **template_data)
		else:
			username = template_data["username"]
			password = template_data["password"]
			email = template_data["email"]
			q = db.GqlQuery("SELECT * from User where name = :1", username)
			if not q.fetch(1):
				pwd_hash = make_pwd_hash(password)
				user = User(name = username, password = pwd_hash, email = email)
				user.put()
				self.writeAuthCookieAndRedirect(user.key().id(), \
												pwd_hash.split("|")[1])
			else:
				template_data["username_error"] = \
						"This username is already taken, please choose another"
				self.write("Signup.html", **template_data)

class CookieUserRequestHandler(base_handler.BaseRequestHandler):
	def get_user_from_cookie(self):
		user_cookie = self.request.cookies.get("user_id", None)
		if user_cookie:
			try:
				id, hash = unicode.split(user_cookie, "|")
				if id.isdigit():	
					user = User.get_by_id(int(id))
					pwd_hash, salt = unicode.split(user.password,"|")
					if (user and \
					 hmac.new(globals()["__SECRET"], salt).hexdigest() == hash):
						return user
			except Exception as e:
				pass

class Login(AuthCookieCreator):
	def get(self):
		self.write("Login.html")
	
	def post(self):
		password = self.request.get('password')
		username = self.request.get('username')
		error = "Invalid login"
		success = False
		if valid_username(username) and valid_password(password):
			q = db.GqlQuery("SELECT * from User where name = :1", username)
			q_fetch = q.fetch(1)
			if len(q_fetch) == 1:
				user = q_fetch[0]
				pwd_hash, salt = unicode.split(user.password, "|")
				if user and (pwd_hash == \
						str.split(make_pwd_hash(password, str(salt)), "|")[0]):
					success = True
					self.writeAuthCookieAndRedirect(user.key().id(), salt)
		if not success:
			self.write("Login.html", username = username, password = "", \
								     error = error)
			
class Logout(AuthCookieCreator):
	def get(self):
		self.writeAuthCookieAndRedirect(None, None)
