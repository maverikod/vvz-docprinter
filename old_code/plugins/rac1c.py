#!/usr/bin/python3

import subprocess
import json
import uuid
from plugins.PluginError import PluginError

msg = None
locale = None

def run(data,inilocale,inimsg):
    # {"cmd":"command name","usr":"username","pwd":"password","params":{params. May be session id, or etc.}}
    msg = inimsg
    locale = inilocale
    if not isinstance(data,dict):
        raise PluginError(code=991,cmd="",errstr="")
    if "cmd" not in data:
        raise PluginError(code=991)
    if data["cmd"].lower() == "sessions":
        rac = rac1c()
        return rac.sessions()
    elif data["cmd"].lower() == "bases":
        rac = rac1c()
        return rac.infobase_list()
    if data["cmd"].lower() == "terminate":
        rac = rac1c()
        if "params" not in data:
            return {"exitcode":985,"data":None}
        if not isinstance(data["params"],dict):
            return {"exitcode":984,"data":None}
        if "session" not in data["params"]:
            return {"exitcode":983,"data":{"propname":"session"}}
        if "message" not in data["params"]:
            return {"exitcode":983,"data":{"propname":"message"}}
        if not isinstance(data["params"]["message"],str):
            return {"exitcode":982,"data":{"propname":"message","proptype":"string"}}
        return rac.session_terminate(data["params"]["session"],data["params"]["message"])
    else:
        raise PluginError(code=989,errstr=data["cmd"])

class rac1c:

    def __init__(self,usr=None,pwd=None):
        #print("RAS1C.__init__")
        self.cluster = self.get_cluster()
        self.usr = usr
        self.pwd = pwd

    def is_valid_uuid(self,uuid_str):
        if isinstance(uuid_str,str):
            try:
                uuid_obj = uuid.UUID(uuid_str)
            except ValueError:
                return False
            return str(uuid_obj) == uuid_str
        return False

    def read_output(self,output,ignore_value_error=False):
        output_dict = {}
        for line in output.strip().split('\n'):
            if len(line) > 0:
                try:                
                    key, value = line.split(':')
                    output_dict[key.strip()] = value.strip()    
                except ValueError:
                    if not ignore_value_error:
                        return None
        return output_dict

    def run_1C_cmd_line_tool(self,cmd):
        res = ['','']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,shell=True)
        try:
            output, error = process.communicate(timeout=5)
            if isinstance(output,bytes):
                res[0] = output.decode('utf-8')
            if isinstance(error,bytes):
                res[1] = error.decode('utf-8')
        except subprocess.TimeoutExpired:
            process.kill()
            output, error = process.communicate()
        return res
    
    def get_cluster(self,return_full_info = False):
        # запускаем приложение
        output = self.run_1C_cmd_line_tool('/usr/bin/rac cluster list')    
        res = self.read_output(output[0])
        #print("get_cluster.res" + str(res))
        if isinstance(res,dict):
            if "cluster" in res.keys():
                return res['cluster']
        if isinstance(res,list):
            while '' in res:
                res.remove('')
            if return_full_info:
                return res

            if len(res) > 0:        
                if "cluster" in res[0].keys():
                    if self.is_valid_uuid(res[0]['cluster']):
                        return res[0]['cluster']

    def sessions(self):
        res = None
        if not isinstance(self.cluster,str):
            self.cluster = self.get_cluster()
        if isinstance(self.cluster,str):
            bases = self.infobase_list()
            if not isinstance(bases,dict):
                bases = {}
            elif not "exitcode" in bases or not "data" in bases:
                bases = {}
            elif not isinstance(bases["data"],dict):
                bases = {}
            else:
                bases = bases["data"]
            output = self.run_1C_cmd_line_tool('/usr/bin/rac session list --cluster '+self.cluster)
            res = {}
            for line in output[0].strip().split('\n\n'):
                body = self.read_output(line,True)
                if "infobase" in body:
                    if "name" in body["infobase"] and "descr" in body["infobase"]:
                        body['infobase-name']  = bases[body["infobase"]]["name"]
                        body['infobase-descr'] = bases[body["infobase"]]["descr"]
                    res[body["session"]] = body
            return {"exitcode":0,"data":res}
        return {"exitcode":987,"data":None} 

    def session_terminate(self,session,errmsg=""):
        res = None
        if not isinstance(self.cluster,str):
            self.cluster = self.get_cluster()
        if isinstance(self.cluster,str) :
            ses_list = self.sessions()
            if ses_list["exitcode"] != 0:
                return ses_list
            else:
                ses_list = ses_list["data"]
            if not session in  ses_list:
                return {"exitcode":988,"data":{"session":session}}
            else:
                output = self.run_1C_cmd_line_tool('/usr/bin/rac session terminate'
                                                   +'  --cluster='+ self.cluster
                                                   +'  --session='+ session
                                                   +'  --error-message="' + errmsg.replace('"', '\\"') + '"'
                                                  )
                ses_list = self.sessions()
                if ses_list["exitcode"] != 0:
                    return ses_list
                else:
                    ses_list = ses_list["data"]
                if session in  ses_list:
                    return {"exitcode":986,"data":{"session":session}}
                #print(output[0])                
        return {"exitcode":0}

    def infobase_list(self):
        res = None
        if isinstance(self.cluster,str):
            output = self.run_1C_cmd_line_tool('/usr/bin/rac infobase summary list --cluster ' + self.cluster)
            res = {}
            for line in output[0].strip().split('\n\n'):
                body = self.read_output(line,True)
                if isinstance(body,dict):
                    if "infobase" in body:
                        res[body["infobase"]] = body

        return {"exitcode":0, "data":res}

    def infobase_info(self,UUID,usr=None,pwd=None):
        res = None
        if usr == None:
            user = self.usr
        else:
            user = usr

        if pwd == None:
            passwd = self.pwd
        else:
            passwd = pwd

        if isinstance(self.cluster,str) and self.is_valid_uuid(UUID):
            output = self.run_1C_cmd_line_tool('/usr/bin/rac infobase info'
                                              +' --cluster       \'' + str(self.cluster) + '\''
                                              +' --infobase      \'' + str(UUID        ) + '\''
                                              +' --infobase-user \'' + str(user        ) + '\''
                                              +' --infobase-pwd  \'' + str(passwd      ) + '\''
                                              )
            if isinstance(output,list):
                if len(output) == 2:
                    if isinstance(output[0],str):
                        body = output[0].strip()
                        if body != '':
                            res = []
                            for line in body.split('\n\n'):
                                res.append(self.read_output(line,True))

        return res

