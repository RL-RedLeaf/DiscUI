
class EventBus:
    def __init__(self):
        self.subscribers = {}               #订阅信息字典

    def subscribe(self,event_type, callback):
        """订阅事件:当event_type事件发生时,调用callback函数"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        return

    def unsubscribe(self, event_type, callback):
        """取消订阅事件:当event_type事件发生时,不再调用callback函数"""
        self.subscribers[event_type].remove(callback)

    def publish(self, event):
        """发布事件：将事件分发给所有订阅者"""
        for event_type, callbacks in self.subscribers.items():
            if isinstance(event, event_type):
                for callback in callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        print(f'ERROR: {e}')