from typing import Sequence

from eth_abi.abi import encode
from eth_hash.auto import keccak

class MerkleTreeGenerator:
    """
    Generates deterministic Merkle Roots following strict Ethereum ABI Encoding.
    Converts raw bytes to 0x-prefixed hex strings.
    """
    
    @staticmethod
    def _to_hex_string(root: bytes) -> str:
        """Converts raw bytes to a 0x-prefixed hex string."""
        return "0x" + root.hex()

    @classmethod
    def hash_nominal_leaf(cls, name: str, pem: str, val: str, sig: str, ts: int) -> bytes:
        encoded = encode(['string', 'string', 'string', 'string', 'uint256'], [name, pem, val, sig, ts])
        return keccak(encoded)
        
    @classmethod
    def hash_tally_leaf(cls, val: str, salt: str) -> bytes:
        encoded = encode(['string', 'string'], [val, salt])
        return keccak(encoded)

    @classmethod
    def hash_eligibility_leaf(cls, name: str, pem: str, sig: str, ts: int) -> bytes:
        encoded = encode(['string', 'string', 'string', 'uint256'], [name, pem, sig, ts])
        return keccak(encoded)

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
                    next_level.append(nodes[i])
                else:
                    # Deterministic pairing: sort the two child nodes before hashing
                    pair = sorted([nodes[i], nodes[i+1]])
                    next_level.append(keccak(pair[0] + pair[1]))
            nodes = next_level
            
        return "0x" + nodes[0].hex()
