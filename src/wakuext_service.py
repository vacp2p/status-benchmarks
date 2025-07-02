# Python Imports
from typing import Dict

# Project Imports
from src.rpc_client import AsyncRpcClient
from src.service import AsyncService


class WakuextAsyncService(AsyncService):
    def __init__(self, async_rpc_client: AsyncRpcClient):
        super().__init__(async_rpc_client, "wakuext")

    async def start_messenger(self):
        response = await self.rpc_request("startMessenger")
        json_response = await response.json()

        if "error" in json_response:
            assert json_response["error"]["code"] == -32000
            assert json_response["error"]["message"] == "messenger already started"
            return

    async def create_community(self, name: str, color="#ffffff", membership: int = 3) -> Dict:
        # TODO check what is membership = 3
        params = [{"membership": membership, "name": name, "color": color, "description": name}]
        response = await self.rpc_request("createCommunity", params)
        return await response.json()

    async def fetch_community(self, community_key: str) -> Dict:
        params = [{"communityKey": community_key, "waitForResponse": True, "tryDatabase": True}]
        response = await self.rpc_request("fetchCommunity", params)
        return await response.json()

    async def request_to_join_community(self, community_id: str, address: str = "fakeaddress") -> Dict:
        params = [{"communityId": community_id, "addressesToReveal": [address], "airdropAddress": address}]
        response = await self.rpc_request("requestToJoinCommunity", params)
        return await response.json()

    async def accept_request_to_join_community(self, request_to_join_id: str) -> Dict:
        params = [{"id": request_to_join_id}]
        response = await self.rpc_request("acceptRequestToJoinCommunity", params)
        return await response.json()

    async def send_chat_message(self, chat_id: str, message: str, content_type: int = 1) -> Dict:
        # TODO content type can always be 1? (plain TEXT), does it need to be community type for communities?
        params = [{"chatId": chat_id, "text": message, "contentType": content_type}]
        response = await self.rpc_request("sendChatMessage", params)
        return await response.json()

    async def send_contact_request(self, contact_id: str, message: str) -> Dict:
        params = [{"id": contact_id, "message": message}]
        response = await self.rpc_request("sendContactRequest", params)
        return await response.json()
