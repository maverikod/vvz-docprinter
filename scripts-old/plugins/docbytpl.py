# cython: language_level=3
import json
import os
import warnings
from docxtpl import DocxTemplate
from jinja2.exceptions import TemplateError,TemplateAssertionError,TemplateRuntimeError,TemplateSyntaxError,UndefinedError,TemplateNotFound
from json import JSONDecodeError
from plugins.utils import read_json
from plugins.utils import plugin_result
from plugins.PluginError import PluginError

def run(data,locale,msg):

    if not isinstance(data,dict):
       return plugin_result(status=992)

    if not "template" in data or not "outfile" in data or not "data" in data:
        return plugin_result(975)
    
    if not os.path.isfile(data["template"]):
        return plugin_result(status=1,data=data["template"])
    try:
        doc = DocxTemplate(data["template"])
        doc.render(data["data"])
    except TemplateNotFound as e:
        return plugin_result(status=985,data=str(e))
    except TemplateAssertionError as e:
        raise PluginError(cmd="docbytpl",code=984,errstr=str(e))
        return plugin_result(status=984,data={"errstr":str(e)})
    except TemplateSyntaxError as e:
        raise PluginError(cmd="docbytpl",code=984,errstr=str(e))
        #return plugin_result(status=984,data={"errstr":str(e)})
    except UndefinedError as e:
        return plugin_result(status=982,data={"errstr":str(e)})
    except TemplateRuntimeError as e:
        return plugin_result(status=981,data={"errstr":str(e)})
    except TemplateError as e:
        return plugin_result(status=986,data={"errstr":str(e)})
    except ValueError as e:
        return plugin_result(status=983,data={"errstr":str(e)})
    
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module='zipfile')
        doc.save(data["outfile"])
        return plugin_result(status=0)
