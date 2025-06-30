# Python Imports
from typing import Dict

# Project Imports
from src.rpc_client import RpcClient
from src.service import Service


class WakuextService(Service):
    def __init__(self, client: RpcClient):
        super().__init__(client, "wakuext")

    def start_messenger(self):
        response = self.rpc_request("startMessenger")
        json_response = response.json()

        if "error" in json_response:
            assert json_response["error"]["code"] == -32000
            assert json_response["error"]["message"] == "messenger already started"
            return

    def create_community(self, name, color="#ffffff", membership=3) -> Dict:
        # TODO check what is membership = 3
        params = [{"membership": membership, "name": name, "color": color, "description": name}]
        response = self.rpc_request("createCommunity", params)
        return response.json()

    def fetch_community(self, community_key) -> Dict:
        params = [{"communityKey": community_key, "waitForResponse": True, "tryDatabase": True}]
        response = self.rpc_request("fetchCommunity", params)
        return response.json()

    def request_to_join_community(self, community_id, address="fakeaddress") -> Dict:
        params = [{"communityId": community_id, "addressesToReveal": [address], "airdropAddress": address}]
        response = self.rpc_request("requestToJoinCommunity", params)
        return response.json()

    def accept_request_to_join_community(self, request_to_join_id) -> Dict:
        params = [{"id": request_to_join_id}]
        response = self.rpc_request("acceptRequestToJoinCommunity", params)
        return response.json()

    def send_chat_message(self, chat_id, message, content_type=1) -> Dict:
        # TODO content type can always be 1? (plain TEXT), does it need to be community type for communities?
        params = [{"chatId": chat_id, "text": message, "contentType": content_type}]
        response = self.rpc_request("sendChatMessage", params)
        return response.json()

    def send_contact_request(self, contact_id: str, message: str) -> Dict:
        params = [{"id": contact_id, "message": message}]
        response = self.rpc_request("sendContactRequest", params)
        return response.json()
