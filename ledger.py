import hashlib

def generate_transaction_hash(transaction_data):
    return hashlib.sha256(transaction_data.encode()).hexdigest()
