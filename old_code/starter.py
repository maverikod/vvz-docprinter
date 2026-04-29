#!/usr/bin/python3
#Format for plugins {"exitcode": int, "data": any type}
import os
import sys
import json
import argparse
from plugins.messages import MessagesContainer
from plugins.PluginError import PluginError
from plugins.utils import log
from plugins.utils import read_json
from plugins.utils import plugin_result
from plugins.utils import openlog
import plugins.docbytpl

def init_paths():
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    module_path = os.path.join(script_dir, "plugins")
    sys.path.append(module_path)
    sys.path.append(script_dir)

def run(indata,logfile, locale='en_US', msg = None):
    status = 0
    try:
        mod = __import__('plugins.' + indata['cmd'])
        #mod = __import__(indata['cmd'])
        mod = getattr(mod,indata['cmd'])
        result = mod.run(indata['data'],locale,msg)
        if not isinstance(result,dict):
            #log(logfile,974,{"cmd":indata["cmd"],"result":str(result)}, locale=locale,msg=msg)
            return plugin_result(status=974,data=str(result))
        if not "exitcode" in result:
            #log(logfile,974,{"cmd":indata["cmd"],"result":str(result)}, locale=locale,msg=msg)
            return plugin_result(status=974,data=str(result))
        elif result["exitcode"] != 0:
            if "data" in result:
                result["errstr"] = msg.getmsg(code=result["exitcode"],locale=locale,data=result["data"])
            else:
                result["errstr"] = msg.getmsg(code=result["exitcode"],locale=locale)
            #print(plugin_result(status=result["exitcode"],data=result["data"],errstr=result["errstr"]))
            return plugin_result(status=result["exitcode"],data=result["data"],errstr=result["errstr"])
        return plugin_result(status=0,data=json.dumps(result,ensure_ascii = False))
    except ModuleNotFoundError as e:
        log(logfile,996, {"cmd":indata["cmd"],"descr": str(e),"path":sys.path}, locale=locale,msg=msg)
        return plugin_result(status=996,data=str(e))
    except ImportError as e:
        log(logfile,996,{"cmd":indata["cmd"],"descr": str(e)}, locale=locale,msg=msg)
        return plugin_result(status=996,data=str(e))
    except AttributeError as e:
        log(logfile,995, {"cmd":indata["cmd"],"descr": str(e)}, locale=locale,msg=msg)
        return plugin_result(status=995,data=str(e))
    except PluginError as e:
        log(logfile,994, {"cmd":indata["cmd"],"errstr":""}, locale=locale,pluginerr=e,msg=msg)
        return plugin_result(status=994,data=str(e))


if __name__ == '__main__':
    init_paths()
    parser = argparse.ArgumentParser()
    parser.add_argument('--infile'  , required=True , type=str, help='Input file name in JSON format')
    parser.add_argument('--lng'     , required=False, type=str, help='Points to language for meesages')
    parser.add_argument('--messages', required=False, type=str, help='File name contained messages')
    try:
        args = parser.parse_args()
        # выполнение вашей программы
    except argparse.ArgumentError as e:
        print(e)
        parser.print_help()
        exit(1)
    except argparse.ArgumentTypeError as e:
        print(e)
        parser.print_help()
        exit(1)

    locale='en_US'
    if hasattr(args,'lng'):
        if isinstance(args.lng,str):
            locale = args.lng

    if hasattr(args,'messages'):
        msg = MessagesContainer(args.messages)
    else:
        msg = MessagesContainer()

    logfile = openlog("/tmp/starter_log.json")

    resp = read_json(args.infile)
    if resp['exitcode'] != 0:
        exit(resp['exitcode'])

    resp = resp["data"]
    if "logfile" in resp:
        if logfile != None:
            logfile.close()
        logfile = openlog(resp["logfile"])

    if not "cmd" in resp:
        log(logfile=logfile,exitcode=978,locale=locale,msg=msg,data={"errstr":resp})
        exit(978)
    
    if not "outfile" in resp:
        log(logfile=logfile,exitcode=977,locale=locale,msg=msg,data={"errstr":resp})
        exit(977)

    outfn = resp["outfile"]
    if os.path.exists(outfn) and len(outfn) == 0:
        os.remove(outfn)
    
    if not "data" in resp:
        log(logfile=logfile,exitcode=976,locale=locale,msg=msg,data={"errstr":resp})
        exit(976)
        
    if 'lng' in resp:
        locale = resp['lng']


    try:
        result = run(resp,logfile,locale=locale,msg=msg)
        if result["exitcode"] != 0:
            log(logfile=logfile,exitcode=result["exitcode"],locale=locale,msg=msg)
            logfile.close()
            exit(result["exitcode"])

        result = result["data"]

        if len(outfn) == 0:
            try:
                with open(outfn, 'w',encoding="utf-8") as f:
                    f.write(result)
                    log(logfile=logfile,exitcode=0,locale=locale,msg=msg)
                    logfile.close()
            except (FileNotFoundError, PermissionError):
                log(logfile,993, {"file":args.outfile},locale=locale,msg=msg)
    except PluginError as e:
        print(str(e))

