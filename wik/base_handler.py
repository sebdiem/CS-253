import webapp2
import jinja2
import os

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_environment = jinja2.Environment( \
    loader=jinja2.FileSystemLoader(template_dir), autoescape=True)

class BaseRequestHandler(webapp2.RequestHandler):
	def __init__(self, *params):
		webapp2.RequestHandler.__init__(self, *params)
		self.jinja = jinja_environment
	
	def render_str(self, template, **params):
		t = self.jinja.get_template(template)
		return t.render(params)
		
	def write(self, template, **params):
		self.response.out.write(self.render_str(template, **params))