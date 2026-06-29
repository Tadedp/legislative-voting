from typing import Sequence

from eth_abi.abi import encode
from eth_hash.auto import keccak

class MerkleTreeGenerator:
    """
    Generates deterministic Merkle Roots following strict Ethereum ABI Encoding.
    Converts raw bytes to 0x-prefixed hex strings.
    """
    @classmethod
    def hash_nominal_leaf(cls, round_id: str, name: str, pem: str, val: str, sig: str, ts: int) -> bytes:
        encoded = encode(['string', 'string', 'string', 'string', 'string', 'uint256'], [round_id, name, pem, val, sig, ts])
        return keccak(b'\x00' + encoded)
        
    @classmethod
    def hash_tally_leaf(cls, round_id: str, val: str, salt: str) -> bytes:
        encoded = encode(['string', 'string', 'string'], [round_id, val, salt])
        return keccak(b'\x00' + encoded)

    @classmethod
    def hash_eligibility_leaf(cls, round_id: str, name: str, pem: str, sig: str, ts: int) -> bytes:
        encoded = encode(['string', 'string', 'string', 'string', 'string', 'uint256'], ["ELIGIBILITY", round_id, name, pem, sig, ts])
        return keccak(b'\x00' + encoded)

    @classmethod
    def hash_tie_breaker_leaf(cls, round_id: str, presiding_officer_id: str, val: str, sig: str, ts: int) -> bytes:
        encoded = encode(['string', 'string', 'string', 'string', 'string', 'uint256'], ["TIE_BREAKER", round_id, presiding_officer_id, val, sig, ts])
        return keccak(b'\x00' + encoded)

    @classmethod
    def generate_tree_root(cls, leaf_hashes: Sequence[bytes]) -> str:
        """
        Generates a Merkle Root from leaf hashes using deterministic lexicographical sorting.
        Returns a '0x'-prefixed hex string for DB/Web3 integration.
        """
        if not leaf_hashes:
            return "0x" + ("00" * 32)
            
        # Deterministic Lexicographical Sort of leaves
        nodes = sorted(leaf_hashes)
        
        # Iteratively pair and hash
        while len(nodes) > 1:
            next_level: list[bytes] = []
            for i in range(0, len(nodes), 2):
                if i + 1 == len(nodes):
                    pair = [nodes[i], nodes[i]]
                    next_level.append(keccak(b'\x01' + pair[0] + pair[1]))
                else:
                    # Deterministic pairing: sort the two child nodes before hashing
                    pair = sorted([nodes[i], nodes[i+1]])
                    next_level.append(keccak(b'\x01' + pair[0] + pair[1]))
            nodes = next_level
            
        return "0x" + nodes[0].hex()
