class RequestContext:
    def __init__(self, user_id: str, chatkit_address: str = None):
        self.user_id = user_id
        self.chatkit_address = chatkit_address