import jinja2
import os

templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(templates_dir), autoescape=True)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)
