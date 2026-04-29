import json
from json import JSONDecodeError
from plugins.messages import MessagesContainer
from plugins.PluginError import PluginError

def plugin_result(status,data={},errstr=""):
    return({"exitcode":status,"data":data,"errstr":errstr})


def read_json(filename):
    result = plugin_result(0)
    try:
        with open(filename, 'r') as file:
            try:
                result["data"] = json.load(file)
                with open(filename, 'r') as f:
                    indata = json.load(f)
                    if not isinstance(indata, dict):
                        return plugin_result(status=998,data=filename)
                    elif 'cmd' not in indata or 'data' not in indata:
                        return plugin_result(status=998,data=filename)
                    return plugin_result(status=0,data=indata)
            except JSONDecodeError as e:
                file.seek(0)
                file_string = file.read()
                error_pos = e.pos
                start_pos = max(0, error_pos-50)
                end_pos = min(len(file_string), error_pos+50)
                return plugin_result(status=3,errstr=e.msg + "==>> " + file_string[start_pos:error_pos] + "<-+->" + file_string[error_pos + 1:end_pos])
            except ValueError as e:
                return plugin_result(status=3,errstr=str(e))
    except FileNotFoundError as e:
        return plugin_result(status=2,data=filename)
    except PermissionError as e:
        return plugin_result(status=11,data=filename)
    except IOError as e:
        return plugin_result(status=979,data=filename)
    except ValueError as e:
        return plugin_result(status=11,data=filename)

def read_json_file(filename,logfile):
    result = read_json(filename)
    return result

def read_input_file(infile,logfile, locale='en_US', msg = None):
    result = read_json(infile)
    return result

def log(logfile,exitcode, data={},msg=None, locale='en_US',pluginerr=None):
    _msg = MessagesContainer() if not isinstance(msg,MessagesContainer) else msg
    exitstr = _msg.getmsg(code=exitcode,locale=locale,data=data)
    if isinstance(pluginerr,PluginError):
        pluginerrstr = _msg.getmsg(code=pluginerr.code,locale=locale,data={"errstr":pluginerr.errstr})
        exitstr = exitstr + ": " + pluginerrstr
    res_str = json.dumps({'exitcode': exitcode, 'exitstr': exitstr},ensure_ascii = False)
    try:
        logfile.write(res_str + '\n')
    except IOError:
        print(res_str)

def openlog(filename):
    try:
        logfile = open(filename, 'w',encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        logfile = None
        log(logfile,993, {"file":filename},locale=locale)
    return logfile