# Python Imports
from typing import Dict

# Project Imports
from src.rpc_client import AsyncRpcClient
from src.service import AsyncService


class WakuextAsyncService(AsyncService):
    def __init__(self, async_rpc_client: AsyncRpcClient):
        super().__init__(async_rpc_client, "wakuext")

    async def start_messenger(self):
        json_response = await self.rpc_request("startMessenger")

        if "error" in json_response:
            assert json_response["error"]["code"] == -32000
            assert json_response["error"]["message"] == "messenger already started"
            return

    async def create_community(self, name: str, color="#ffffff", membership: int = 3, history_archive_support_enabled=False) -> dict:
        # TODO check what is membership = 3
        params = [{"membership": membership, "name": name, "color": color, "description": name,
                   "historyArchiveSupportEnabled": history_archive_support_enabled}]
        json_response = await self.rpc_request("createCommunity", params)
        return json_response

    async def create_community_chat(self, community_id: str, c: dict):
        params = [community_id, c]
        json_response = await self.rpc_request("createCommunityChat", params)
        return json_response

    async def fetch_community(self, community_key: str) -> dict:
        params = [{"communityKey": community_key, "waitForResponse": True, "tryDatabase": True}]
        json_response = await self.rpc_request("fetchCommunity", params)
        return json_response

    async def request_to_join_community(self, community_id: str, address: str = "fakeaddress") -> dict:
        params = [{"communityId": community_id, "addressesToReveal": [address], "airdropAddress": address}]
        json_response = await self.rpc_request("requestToJoinCommunity", params)
        return json_response

    async def accept_request_to_join_community(self, request_to_join_id: str) -> dict:
        params = [{"id": request_to_join_id}]
        json_response = await self.rpc_request("acceptRequestToJoinCommunity", params)
        return json_response

    async def decline_request_to_join_community(self, request_to_join_id: str) -> dict:
        params = [{"id": request_to_join_id}]
        json_response = await self.rpc_request("declineRequestToJoinCommunity", params)
        return json_response

    async def send_chat_message(self, chat_id: str, message: str, content_type: int = 1) -> dict:
        # TODO content type can always be 1? (plain TEXT), does it need to be community type for communities?
        params = [{"chatId": chat_id, "text": message, "contentType": content_type}]
        json_response = await self.rpc_request("sendChatMessage", params)
        return json_response

    async def send_contact_request(self, contact_id: str, message: str) -> Dict:
        params = [{"id": contact_id, "message": message}]
        json_response = await self.rpc_request("sendContactRequest", params)
        return json_response

    async def accept_contact_request(self, request_id: str) -> dict:
        params = [{"id": request_id}]
        json_response = await self.rpc_request("acceptContactRequest", params)
        return json_response

    async def decline_contact_request(self, request_id: str) -> dict:
        params = [{"id": request_id}]
        json_response = await self.rpc_request("declineContactRequest", params)
        return json_response

    async def send_one_to_one_message(self, contact_id: str, message: str):
        params = [{"id": contact_id, "message": message}]
        json_response = await self.rpc_request("sendOneToOneMessage", params)
        return json_response

    async def create_group_chat_with_members(self, pubkey_list: list, group_chat_name: str):
        params = [None, group_chat_name, pubkey_list]
        json_response = await self.rpc_request("createGroupChatWithMembers", params)
        return json_response

    async def send_group_chat_message(self, group_id: str, message: str):
        params = [{"id": group_id, "message": message}]
        json_response = await self.rpc_request("sendGroupChatMessage", params)
        return json_response

    async def add_contact(self, contact_id: str, displayName: str):
        params = [{"id": contact_id, "nickname": "fake_nickname", "displayName": displayName, "ensName": ""}]
        json_response = await self.rpc_request("addContact", params)
        return json_response

    async def get_peer_id(self):
        json_response = await self.rpc_request("peerID", [])
        return json_response

    async def set_archive_distribution_preference(self, preference: str):
        params = [{"preference": preference}]
        response = await self.rpc_request("setArchiveDistributionPreference", params)
        return response

    async def get_message_archival(self):
        json_response = await self.rpc_request("getMessageArchiveInterval", [])
        return json_response

    async def has_community_archive(self, community_id: str):
        params = [community_id]
        json_response = await self.rpc_request("hasCommunityArchive", params)
        return json_response

    async def debug(self):
        params = []
        json_response = await self.rpc_request("debug", params)
        return json_response

    async def connect(self, peerId: str, addrs: list = []):
        params = [peerId, addrs]
        response = await self.rpc_request("connect", params)
        return response
