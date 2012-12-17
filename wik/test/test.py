import unittest
import string
import os
import webapp2
import random

from google.appengine.ext import testbed
import wik.login as login
import wik.wiki as wiki

BASE_URL = "http://localhost:8081"

def generate_invalid_usernames():
	allowed_characters = ["-","_"]
	invalid_characters = string.punctuation + string.whitespace
	for c in allowed_characters:
		invalid_characters = string.replace(invalid_characters, c, "")
	result = []
	# too short:
	result.append("a")
	# too long:
	result.append(string.letters)
	# invalid characters:
	for c in invalid_characters:
		result.append("seb%sastien" % c)
	result.append("seb@stien")
	return result

def generate_invalid_passwords():
	result = []
	# too short:
	result.append("a")
	# too long:
	result.append("1234567891011121314151617181920")
	return result

def generate_invalid_emails():
	result = []
	# missing @:
	result.append("abcdefg.com")
	# missing .:
	result.append("abcdefg@com")
	# missing domain:
	result.append("abcdefg@")
	# missing prefix:
	result.append("@example.com")
	return result
	
class TestValidationFunctions(unittest.TestCase):
	def test_valid_username(self):
		for username in generate_invalid_usernames():
			self.assertTrue(not login.valid_username(username))
		# valid:
		self.assertTrue(login.valid_username("sebastien"))
	
	def test_valid_password(self):
		for pwd in generate_invalid_passwords():
			self.assertTrue(not login.valid_password(pwd))
		# valid:
		self.assertTrue(login.valid_password("hunter!2"))
	
	def test_valid_verify(self):
		self.assertTrue(login.valid_verify("password","password"))
	
	def test_valid_email(self):
		for email in generate_invalid_emails():
			self.assertTrue(not login.valid_email(email))
		# ok:
		self.assertTrue(login.valid_email("test@example.com"))
		# ok:
		self.assertTrue(login.valid_email(""))
		
class TestUserAuthentification(unittest.TestCase):
	def setUp(self):
		# First, create an instance of the Testbed class.
		self.testbed = testbed.Testbed()
		# Then activate the testbed, which prepares the service stubs for use.
		self.testbed.activate()
		# Next, declare which service stubs you want to use.
		self.testbed.init_datastore_v3_stub(require_indexes=True, \
								root_path="%s/../" % os.path.dirname(__file__))
		self.testbed.init_memcache_stub()
		
	def tearDown(self):
		self.testbed.deactivate()
	
	def find_unused_username(self):
		test_name = "test"
		while self.user_in_db(test_name):
			test_name = test_name + str(random.choice(range(100)))
		return test_name
	
	def get(self, path):
		request = webapp2.Request.blank(path=path)
		response = request.get_response(wiki.app)
		return response
		
	def _send_data(self, path, data):
		request = webapp2.Request.blank(path=path, POST=data)
		response = request.get_response(wiki.app)
		return response
		
	def _test_cookie(self, resp):
		cookie = resp.headers['Set-Cookie']
		user_id_end = cookie.find("|")
		return (cookie[:8] == "user_id=") and cookie[8:user_id_end].isdigit()
						
	def send_wrong_data(self, path, data):
		resp = self._send_data(path, data)
		# no redirect because data is invalid
		self.assertEqual(resp.status_int, 200)
		return resp
	
	def send_valid_data(self, path, data):
		resp = self._send_data(path, data)
		# redirect expected because data is valid
		self.assertEqual(resp.status_int, 302)
		return resp
			
	def user_in_db(self, user):
		gql = login.User.gql("WHERE name = :1", user)
		return (len(gql.fetch(1)) == 1)
		
class TestSignup(TestUserAuthentification):
	def create_data(self, username, password, verify, email):
		return {"username":username, "password":password, "verify":verify, \
				"email":email}
				
	def test_wrong_verify_password(self):
		test_name = self.find_unused_username()
		data = self.create_data(test_name,"tutu","toutou","")
		resp = self.send_wrong_data('/signup', data)
		# check that the user has not been entered in the db:
		self.assertTrue(not self.user_in_db(test_name))
		
	def test_wrong_username(self):
		for username in generate_invalid_usernames():
			data = self.create_data(username,"tutu","tutu","")
			resp = self.send_wrong_data('/signup', data)
			# check that the user has not been entered in the db:
			self.assertTrue(not self.user_in_db(username))
	
	def test_wrong_password(self):
		test_name = self.find_unused_username()
		for pwd in generate_invalid_passwords():
			data = self.create_data(test_name,pwd,pwd,"")
			resp = self.send_wrong_data('/signup', data)
			# check that the user has not been entered in the db:
			self.assertTrue(not self.user_in_db(test_name))
			
	def test_wrong_email(self):
		test_name = self.find_unused_username()
		for email in generate_invalid_emails():
			data = self.create_data(test_name,"tutu","tutu",email)
			resp = self.send_wrong_data('/signup', data)
			# check that the user has not been entered in the db:
			self.assertTrue(not self.user_in_db(test_name))
	
	def test_valid_user(self):
		test_name = self.find_unused_username()
		data = self.create_data(test_name,"tutu","tutu","")
		resp = self.send_valid_data('/signup', data)
		self.assertTrue(self.user_in_db(test_name))
		test_name = self.find_unused_username()
		data = self.create_data(test_name,"tutu","tutu","test@test.com")
		resp = self.send_valid_data('/signup', data)
		self.assertTrue(self.user_in_db(test_name))
	
	def test_duplicated_user(self):
		test_name = self.find_unused_username()
		data = self.create_data(test_name,"tutu","tutu","")
		resp = self.send_valid_data('/signup', data)
		self.assertTrue(self.user_in_db(test_name))
		resp = self.send_wrong_data('/signup', data)
	
	def test_cookie(self):
		test_name = "test_toto"
		data = self.create_data(test_name,"tutu","tutu","")
		resp = self.send_valid_data('/signup', data)
		self.assertTrue(self._test_cookie(resp))

class TestLogin(TestUserAuthentification):
	def create_data(self, username, password):
		return {"username":username, "password":password}
		
	def test_unknown_user(self):
		test_name = "toto"
		while self.user_in_db(test_name):
			test_name = test_name + random.choice(range(100))
		data = self.create_data(test_name, "pass")
		self.send_wrong_data('/login', data)
	
	def test_wrong_password(self):
		test_name = "toto"
		pwd = "hunter2!"
		wrong_pwd = "wrong_password"
		while self.user_in_db(test_name):
			test_name = test_name + random.choice(range(100))
		self.send_valid_data('/signup', {"username":test_name, "password":pwd, \
								  "verify":pwd, "email":""})
		if self.user_in_db(test_name):
			data = self.create_data(test_name, wrong_pwd)
			self.send_wrong_data('/login', data)
		else:
			raise Exception("Test failed user not entered in db")
	
	def test_valid_user(self):
		test_name = "toto"
		pwd = "hunter2!"
		while self.user_in_db(test_name):
			test_name = test_name + random.choice(range(100))
		self.send_valid_data('/signup', {"username":test_name, "password":pwd, \
								  "verify":pwd, "email":""})
		if self.user_in_db(test_name):
			data = self.create_data(test_name, pwd)
			resp = self.send_valid_data('/login', data)
			self.assertTrue(self._test_cookie(resp))
		else:
			raise Exception("Test failed user not entered in db")

class TestLogout(TestUserAuthentification):
	def test_logout(self):
		resp = self.get('/logout')
		self.assertEqual(resp.status_int, 302)
		self.assertFalse(self._test_cookie(resp))

if __name__ == '__main__':
    unittest.main()

def run():
	suite = unittest.TestLoader().discover("wik.test")
	unittest.TextTestRunner(verbosity=2).run(suite)