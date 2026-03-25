from dataclasses import dataclass

from django.conf import settings

from dj_wallet.anchor import ChainAdapter


class MissingDependency(RuntimeError):
    pass


def _require_web3():
    try:
        from web3 import Web3
    except Exception as exc:  # pragma: no cover - import guard
        raise MissingDependency(
            "web3 is required for BesuAdapter. Install dj-wallet[chain]."
        ) from exc
    return Web3


ANCHOR_ABI = [
    {
        "inputs": [{"internalType": "bytes32", "name": "hash", "type": "bytes32"}],
        "name": "anchor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


@dataclass
class BesuConfig:
    rpc_url: str
    private_key: str
    contract_address: str
    chain_id: int
    gas: int = 200000


class BesuAdapter(ChainAdapter):
    """
    Besu on-chain adapter using JSON-RPC.
    Requires DJ_WALLET_CHAIN_RPC_URL, DJ_WALLET_CHAIN_PRIVATE_KEY,
    DJ_WALLET_ANCHOR_CONTRACT_ADDRESS, DJ_WALLET_CHAIN_ID.
    """

    def __init__(self):
        Web3 = _require_web3()
        self.w3 = Web3(Web3.HTTPProvider(self._config().rpc_url))
        self.account = self.w3.eth.account.from_key(self._config().private_key)
        self.contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(self._config().contract_address),
            abi=ANCHOR_ABI,
        )

    def _config(self):
        return BesuConfig(
            rpc_url=getattr(settings, "DJ_WALLET_CHAIN_RPC_URL", "http://127.0.0.1:8545"),
            private_key=getattr(settings, "DJ_WALLET_CHAIN_PRIVATE_KEY", ""),
            contract_address=getattr(settings, "DJ_WALLET_ANCHOR_CONTRACT_ADDRESS", ""),
            chain_id=int(getattr(settings, "DJ_WALLET_CHAIN_ID", 0)),
            gas=int(getattr(settings, "DJ_WALLET_ANCHOR_GAS", 200000)),
        )

    def submit_hash(self, tx_hash):
        if not self._config().private_key:
            raise RuntimeError("DJ_WALLET_CHAIN_PRIVATE_KEY is not set")
        if not self._config().contract_address:
            raise RuntimeError("DJ_WALLET_ANCHOR_CONTRACT_ADDRESS is not set")
        if not self._config().chain_id:
            raise RuntimeError("DJ_WALLET_CHAIN_ID is not set")

        # Convert sha256 hex to bytes32
        if tx_hash.startswith("0x"):
            hex_hash = tx_hash[2:]
        else:
            hex_hash = tx_hash
        if len(hex_hash) != 64:
            raise ValueError("tx_hash must be 32 bytes hex")

        hash_bytes = bytes.fromhex(hex_hash)

        nonce = self.w3.eth.get_transaction_count(self.account.address)
        gas_price = self.w3.eth.gas_price

        tx = self.contract.functions.anchor(hash_bytes).build_transaction(
            {
                "from": self.account.address,
                "nonce": nonce,
                "chainId": self._config().chain_id,
                "gas": self._config().gas,
                "gasPrice": gas_price,
            }
        )
        signed = self.w3.eth.account.sign_transaction(tx, self._config().private_key)
        tx_hash_bytes = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return tx_hash_bytes.hex()

    def check_confirmation(self, onchain_tx_hash):
        if not onchain_tx_hash:
            return False
        try:
            receipt = self.w3.eth.get_transaction_receipt(onchain_tx_hash)
        except Exception:
            return False
        return receipt is not None and receipt.get("status", 0) == 1
