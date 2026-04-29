class PluginError(Exception):
    def __init__(self, code, errstr=None,cmd = None) -> None:
        self.code = int(code)
        self.errstr = str(errstr)
        self.cmd = str(cmd)
        super().__init__(self.code)

