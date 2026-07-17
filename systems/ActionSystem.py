
class ActionSystem:
    def __init__(self):
        pass

    def setup(self, register_dict: dict) -> bool:
        '''设置注册表, 此处返回 bool 用以表示注册表是否成功设置'''
        self.register_dict = register_dict
        return True
