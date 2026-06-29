import json
from typing import Any

from web3 import AsyncWeb3
from web3.exceptions import ContractCustomError
from eth_typing import ChecksumAddress

class BlockchainNotaryService:
    """
    AsyncWeb3 integration with the Polygon Amoy smart contract.
    """
    def __init__(self, rpc_url: str, private_key: str, contract_address: str, abi_path: str):
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        self.private_key = private_key
        self.account = self.w3.eth.account.from_key(private_key)

        self.contract_address: ChecksumAddress = self.w3.to_checksum_address(contract_address)
        
        with open(abi_path, 'r') as f:
            contract_data = json.load(f)
            self.contract_abi = contract_data.get('abi', contract_data)
            
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.contract_abi)

    async def proclaim_round(
        self,
        round_id: str,
        title: str,
        is_nominal: bool,
        nominal_root: str,
        tally_root: str,
        eligibility_root: str
    ) -> dict[str, Any]:
        """
        Broadcasts the proclaimRound transaction asynchronously.
        Returns a dict with 'transaction_hash' and 'block_number'.
        Recovers from 'AlreadyProclaimed' errors by scraping Event Logs.
        """
        nonce = await self.w3.eth.get_transaction_count(self.account.address, 'pending')
        
        tx_build = await self.contract.functions.proclaimRound(
            round_id,
            title,
            is_nominal,
            bytes.fromhex(nominal_root[2:]),
            bytes.fromhex(tally_root[2:]),
            bytes.fromhex(eligibility_root[2:])
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx_build, private_key=self.private_key)
        
        try:
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt.get("status") != 1:
                raise Exception(f"Transaction failed on-chain: {receipt.get('transactionHash', b'').hex()}")
            return {
                "transaction_hash": receipt.get("transactionHash", b"").hex(),
                "block_number": receipt.get("blockNumber", 0)
            }
        except ContractCustomError as e:
            # Parse the custom error to catch AlreadyProclaimed()
            if "AlreadyProclaimed" in str(e):
                return await self.recover_from_event_logs(round_id)
            raise e
        except Exception as e:
            raise e

    async def recover_from_event_logs(self, round_id: str) -> dict[str, Any]:
        """
        Queries the blockchain for the RoundProclaimed event specific to this round_id.
        Extracts the transaction_hash and block_number to allow PostgreSQL to sync.
        """
        latest_block = await self.w3.eth.block_number
        from_block = max(0, latest_block - 1000)
        
        events = await self.contract.events.RoundProclaimed.get_logs(fromBlock=from_block, toBlock='latest')
        for event in events:
            if event.args.roundId == round_id:
                return {
                    "transaction_hash": event.transactionHash.hex(),
                    "block_number": event.blockNumber
                }
                
        raise Exception(f"Failed to recover logs: RoundProclaimed event not found for {round_id}")
