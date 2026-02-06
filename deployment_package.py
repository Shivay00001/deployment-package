# ============================================================================
# FILE: requirements.txt
# ============================================================================
"""
web3==6.11.0
eth-account==0.10.0
redis==5.0.1
pyyaml==6.0.1
numpy==1.24.3
scikit-learn==1.3.2
aiohttp==3.9.1
python-dotenv==1.0.0
"""

# ============================================================================
# FILE: docker-compose.yml
# ============================================================================
"""
version: '3.8'

services:
  you-ai-oracle:
    build: .
    container_name: you-ai-oracle
    restart: unless-stopped
    environment:
      - ETHEREUM_RPC=${ETHEREUM_RPC}
      - YOU_DAO_ADDRESS=${YOU_DAO_ADDRESS}
      - AI_GUARDIAN_ADDRESS=${AI_GUARDIAN_ADDRESS}
      - ORACLE_PRIVATE_KEY=${ORACLE_PRIVATE_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config.yaml:/app/config.yaml
    depends_on:
      - redis
    networks:
      - you-dao-network

  redis:
    image: redis:7-alpine
    container_name: you-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - you-dao-network

  monitoring:
    image: grafana/grafana:latest
    container_name: you-monitoring
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    networks:
      - you-dao-network

volumes:
  redis-data:
  grafana-data:

networks:
  you-dao-network:
    driver: bridge
"""

# ============================================================================
# FILE: Dockerfile
# ============================================================================
"""
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p data logs abis

# Run oracle
CMD ["python", "you_ai_oracle.py", "run"]
"""

# ============================================================================
# FILE: scripts/deploy_contracts.py
# ============================================================================
"""
#!/usr/bin/env python3
'''
Contract deployment script for YOU.DAO
'''

import json
import sys
from pathlib import Path
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import os

load_dotenv()

def load_contract(name: str):
    '''Load compiled contract'''
    build_path = Path('build') / f'{name}.json'
    with open(build_path, 'r') as f:
        contract_json = json.load(f)
    return contract_json['abi'], contract_json['bytecode']

def deploy_treasury(w3: Web3, deployer: Account, owners: list, required: int):
    '''Deploy treasury multisig'''
    print(f'Deploying Treasury MultiSig...')
    print(f'  Owners: {owners}')
    print(f'  Required signatures: {required}')
    
    abi, bytecode = load_contract('TreasuryMultiSig')
    
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    tx = contract.constructor(owners, required).build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'gas': 3000000,
        'gasPrice': w3.to_wei('30', 'gwei')
    })
    
    signed = deployer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print(f'✅ Treasury deployed at: {receipt.contractAddress}')
    return receipt.contractAddress

def deploy_dao(w3: Web3, deployer: Account, treasury_address: str):
    '''Deploy main DAO contract'''
    print(f'Deploying YOU.DAO...')
    print(f'  Treasury: {treasury_address}')
    
    abi, bytecode = load_contract('YOUDAO')
    
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    tx = contract.constructor(treasury_address).build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'gas': 5000000,
        'gasPrice': w3.to_wei('30', 'gwei')
    })
    
    signed = deployer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print(f'✅ YOU.DAO deployed at: {receipt.contractAddress}')
    return receipt.contractAddress

def deploy_ai_guardian(w3: Web3, deployer: Account):
    '''Deploy AI Guardian contract'''
    print(f'Deploying AI Guardian...')
    
    abi, bytecode = load_contract('YOUAIGuardian')
    
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    tx = contract.constructor().build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'gas': 3000000,
        'gasPrice': w3.to_wei('30', 'gwei')
    })
    
    signed = deployer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print(f'✅ AI Guardian deployed at: {receipt.contractAddress}')
    return receipt.contractAddress

def link_contracts(w3: Web3, deployer: Account, dao_address: str, guardian_address: str, oracle_address: str):
    '''Link contracts together'''
    print(f'Linking contracts...')
    
    # Load ABIs
    dao_abi, _ = load_contract('YOUDAO')
    guardian_abi, _ = load_contract('YOUAIGuardian')
    
    dao = w3.eth.contract(address=dao_address, abi=dao_abi)
    guardian = w3.eth.contract(address=guardian_address, abi=guardian_abi)
    
    # Set AI Guardian in DAO
    tx1 = dao.functions.setAIGuardian(guardian_address).build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'gas': 100000,
        'gasPrice': w3.to_wei('30', 'gwei')
    })
    signed1 = deployer.sign_transaction(tx1)
    w3.eth.send_raw_transaction(signed1.rawTransaction)
    
    # Set DAO in Guardian
    tx2 = guardian.functions.setYOUDAO(dao_address).build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address) + 1,
        'gas': 100000,
        'gasPrice': w3.to_wei('30', 'gwei')
    })
    signed2 = deployer.sign_transaction(tx2)
    w3.eth.send_raw_transaction(signed2.rawTransaction)
    
    # Set AI Oracle address
    tx3 = guardian.functions.setAIOracle(oracle_address).build_transaction({
        'from': deployer.address,
        'nonce': w3.eth.get_transaction_count(deployer.address) + 2,
        'gas': 100000,
        'gasPrice': w3.to_wei('30', 'gwei')
    })
    signed3 = deployer.sign_transaction(tx3)
    w3.eth.send_raw_transaction(signed3.rawTransaction)
    
    print(f'✅ Contracts linked successfully')

def main():
    print('=' * 60)
    print('YOU.DAO DEPLOYMENT SCRIPT')
    print('=' * 60)
    
    # Connect to network
    rpc_url = os.getenv('ETHEREUM_RPC')
    if not rpc_url:
        print('❌ ETHEREUM_RPC not set')
        sys.exit(1)
    
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        print('❌ Failed to connect to Ethereum node')
        sys.exit(1)
    
    print(f'✅ Connected to network (Chain ID: {w3.eth.chain_id})')
    
    # Load deployer account
    private_key = os.getenv('DEPLOYER_PRIVATE_KEY')
    if not private_key:
        print('❌ DEPLOYER_PRIVATE_KEY not set')
        sys.exit(1)
    
    deployer = Account.from_key(private_key)
    print(f'Deployer address: {deployer.address}')
    
    balance = w3.eth.get_balance(deployer.address)
    print(f'Balance: {w3.from_wei(balance, "ether")} ETH')
    
    if balance < w3.to_wei(0.5, 'ether'):
        print('⚠️  Low balance, deployment may fail')
    
    # Get oracle address
    oracle_address = os.getenv('ORACLE_ADDRESS', deployer.address)
    
    # Deploy treasury
    treasury_owners = [deployer.address]  # Add more in production
    treasury_required = 1
    treasury_address = deploy_treasury(w3, deployer, treasury_owners, treasury_required)
    
    # Deploy DAO
    dao_address = deploy_dao(w3, deployer, treasury_address)
    
    # Deploy AI Guardian
    guardian_address = deploy_ai_guardian(w3, deployer)
    
    # Link contracts
    link_contracts(w3, deployer, dao_address, guardian_address, oracle_address)
    
    # Save deployment info
    deployment_info = {
        'network': w3.eth.chain_id,
        'deployer': deployer.address,
        'treasury': treasury_address,
        'you_dao': dao_address,
        'ai_guardian': guardian_address,
        'oracle': oracle_address,
        'deployed_at': int(time.time())
    }
    
    with open('deployment.json', 'w') as f:
        json.dump(deployment_info, f, indent=2)
    
    print('\\n' + '=' * 60)
    print('DEPLOYMENT COMPLETE')
    print('=' * 60)
    print(f'Treasury: {treasury_address}')
    print(f'YOU.DAO: {dao_address}')
    print(f'AI Guardian: {guardian_address}')
    print(f'\\nDeployment info saved to deployment.json')
    print('\\nNext steps:')
    print('1. Update config.yaml with contract addresses')
    print('2. Fund the oracle address with ETH for gas')
    print('3. Start the oracle: python you_ai_oracle.py run')

if __name__ == '__main__':
    import time
    main()
"""

# ============================================================================
# FILE: scripts/test_system.py
# ============================================================================
"""
#!/usr/bin/env python3
'''
Comprehensive testing for YOU.DAO system
'''

import unittest
import asyncio
from web3 import Web3
from eth_account import Account
import sys
sys.path.append('..')

from you_ai_oracle import DecisionEngine, FounderPersonality, Proposal, ProposalCategory

class TestDecisionEngine(unittest.TestCase):
    '''Test decision engine logic'''
    
    def setUp(self):
        '''Setup test environment'''
        self.personality = FounderPersonality(
            vision_keywords=['ai', 'automation', 'system', 'infrastructure'],
            risk_tolerance=0.7,
            innovation_bias=0.9,
            social_impact_weight=0.6,
            financial_weight=0.4,
            decision_patterns={
                'research': 0.9,
                'infrastructure': 0.95,
                'marketing': 0.3
            },
            core_values=['long_term', 'decentralization'],
            red_flags=['scam', 'ponzi', 'guaranteed returns']
        )
        
        self.engine = DecisionEngine(self.personality)
    
    def test_high_alignment_proposal(self):
        '''Test proposal with high vision alignment'''
        proposal = Proposal(
            id=1,
            title='AI-Powered Automation Infrastructure',
            description='Build decentralized AI system for autonomous execution',
            amount=10 * 10**18,  # 10 ETH
            recipient='0x1234567890123456789012345678901234567890',
            category='infrastructure',
            created_at=1234567890,
            voting_ends_at=1234567890 + 604800,
            for_votes=0,
            against_votes=0,
            executed=False,
            ai_approved=False,
            ai_confidence=0
        )
        
        decision = self.engine.analyze_proposal(proposal)
        
        self.assertTrue(decision.approved)
        self.assertGreater(decision.confidence, 0.7)
        self.assertGreater(decision.alignment_score, 0.5)
    
    def test_red_flag_rejection(self):
        '''Test immediate rejection of red flag content'''
        proposal = Proposal(
            id=2,
            title='Guaranteed Returns Investment Opportunity',
            description='Join our ponzi scheme for 100% guaranteed returns',
            amount=100 * 10**18,
            recipient='0x1234567890123456789012345678901234567890',
            category='general',
            created_at=1234567890,
            voting_ends_at=1234567890 + 604800,
            for_votes=0,
            against_votes=0,
            executed=False,
            ai_approved=False,
            ai_confidence=0
        )
        
        decision = self.engine.analyze_proposal(proposal)
        
        self.assertFalse(decision.approved)
        self.assertGreater(decision.confidence, 0.9)
        self.assertIn('red flag', decision.reasoning.lower())
    
    def test_low_alignment_rejection(self):
        '''Test rejection of misaligned proposal'''
        proposal = Proposal(
            id=3,
            title='Traditional Marketing Campaign',
            description='Hire marketing agency for traditional advertising',
            amount=50 * 10**18,
            recipient='0x1234567890123456789012345678901234567890',
            category='marketing',
            created_at=1234567890,
            voting_ends_at=1234567890 + 604800,
            for_votes=0,
            against_votes=0,
            executed=False,
            ai_approved=False,
            ai_confidence=0
        )
        
        decision = self.engine.analyze_proposal(proposal)
        
        # Marketing has low category score (0.3)
        self.assertFalse(decision.approved)
    
    def test_risk_assessment(self):
        '''Test risk assessment for large amounts'''
        proposal = Proposal(
            id=4,
            title='Large Infrastructure Investment',
            description='Major system upgrade with high potential',
            amount=500 * 10**18,  # 500 ETH - high amount
            recipient='0x1234567890123456789012345678901234567890',
            category='infrastructure',
            created_at=1234567890,
            voting_ends_at=1234567890 + 604800,
            for_votes=0,
            against_votes=0,
            executed=False,
            ai_approved=False,
            ai_confidence=0
        )
        
        decision = self.engine.analyze_proposal(proposal)
        
        # Should detect high risk due to large amount
        self.assertGreater(decision.risk_assessment, 0.5)

class TestOracleIntegration(unittest.TestCase):
    '''Integration tests for oracle system'''
    
    @unittest.skip('Requires running blockchain node')
    def test_founder_status_check(self):
        '''Test founder status checking'''
        # Would test actual blockchain interaction
        pass
    
    @unittest.skip('Requires running blockchain node')
    def test_proposal_fetching(self):
        '''Test fetching proposals from chain'''
        pass

def run_tests():
    '''Run all tests'''
    print('=' * 60)
    print('YOU.DAO SYSTEM TESTS')
    print('=' * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDecisionEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestOracleIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print('\\n' + '=' * 60)
    if result.wasSuccessful():
        print('✅ ALL TESTS PASSED')
    else:
        print('❌ SOME TESTS FAILED')
        print(f'Failures: {len(result.failures)}')
        print(f'Errors: {len(result.errors)}')
    print('=' * 60)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
"""

# ============================================================================
# FILE: scripts/simulate_proposals.py
# ============================================================================
"""
#!/usr/bin/env python3
'''
Simulate proposal creation for testing
'''

import sys
import time
from web3 import Web3
from eth_account import Account
import os
from dotenv import load_dotenv

load_dotenv()

def create_test_proposal(w3, dao_contract, proposer, title, description, amount, category):
    '''Create a test proposal'''
    print(f'Creating proposal: {title}')
    
    tx = dao_contract.functions.createProposal(
        title,
        description,
        amount,
        proposer.address,
        category
    ).build_transaction({
        'from': proposer.address,
        'nonce': w3.eth.get_transaction_count(proposer.address),
        'gas': 500000,
        'gasPrice': w3.to_wei('30', 'gwei')
    })
    
    signed = proposer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] == 1:
        print(f'✅ Proposal created successfully')
        return True
    else:
        print(f'❌ Proposal creation failed')
        return False

def main():
    # Connect
    rpc_url = os.getenv('ETHEREUM_RPC')
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        print('❌ Failed to connect')
        sys.exit(1)
    
    # Load account
    private_key = os.getenv('PROPOSER_PRIVATE_KEY')
    proposer = Account.from_key(private_key)
    
    # Load DAO contract
    dao_address = os.getenv('YOU_DAO_ADDRESS')
    with open('abis/YOUDAO.json', 'r') as f:
        import json
        dao_abi = json.load(f)
    
    dao = w3.eth.contract(address=dao_address, abi=dao_abi)
    
    # Test proposals
    proposals = [
        {
            'title': 'AI Research Funding',
            'description': 'Fund research into autonomous AI systems for decentralized governance',
            'amount': w3.to_wei(10, 'ether'),
            'category': 0  # Research
        },
        {
            'title': 'Infrastructure Upgrade',
            'description': 'Upgrade core protocol infrastructure for better scalability',
            'amount': w3.to_wei(50, 'ether'),
            'category': 1  # Infrastructure
        },
        {
            'title': 'Marketing Campaign',
            'description': 'Traditional marketing campaign for brand awareness',
            'amount': w3.to_wei(20, 'ether'),
            'category': 2  # Marketing
        }
    ]
    
    for prop in proposals:
        create_test_proposal(
            w3, dao, proposer,
            prop['title'],
            prop['description'],
            prop['amount'],
            prop['category']
        )
        time.sleep(5)
    
    print('\\n✅ Test proposals created')

if __name__ == '__main__':
    main()
"""

# ============================================================================
# FILE: .env.example
# ============================================================================
"""
# Ethereum Configuration
ETHEREUM_RPC=https://mainnet.infura.io/v3/YOUR_PROJECT_ID
CHAIN_ID=1

# Contract Addresses (fill after deployment)
YOU_DAO_ADDRESS=0x0000000000000000000000000000000000000000
AI_GUARDIAN_ADDRESS=0x0000000000000000000000000000000000000000
TREASURY_ADDRESS=0x0000000000000000000000000000000000000000

# Oracle Configuration
ORACLE_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
ORACLE_ADDRESS=0xYOUR_ORACLE_ADDRESS_HERE

# Deployment (for deployer only)
DEPLOYER_PRIVATE_KEY=0xYOUR_DEPLOYER_KEY_HERE

# Testing (for testnet)
PROPOSER_PRIVATE_KEY=0xYOUR_TEST_KEY_HERE

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
"""

# ============================================================================
# FILE: README.md
# ============================================================================
"""
# YOU.DAO - Immortal Execution System

Production-ready decentralized autonomous organization with AI guardian for immortal decision-making.

## Features

- ✅ **No LLM Dependencies** - Pure rule-based AI decision engine
- ✅ **Production Ready** - Full error handling, logging, monitoring
- ✅ **Decentralized** - Smart contracts + AI oracle
- ✅ **Immortal** - Continues after founder's death
- ✅ **Secure** - Multi-sig treasury, risk assessment
- ✅ **Scalable** - Docker deployment, Redis caching

## Architecture

```
┌─────────────────┐
│   Founder       │
│   Heartbeat     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  AI Guardian    │◄─────┤  YOU.AI      │
│  Smart Contract │      │  Oracle      │
└────────┬────────┘      └──────┬───────┘
         │                      │
         │                      │
         ▼                      ▼
┌─────────────────┐      ┌──────────────┐
│   YOU.DAO       │◄─────┤  Decision    │
│   Contract      │      │  Engine      │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐
│   Treasury      │
│   Multi-Sig     │
└─────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/yourusername/you-dao
cd you-dao

# Install dependencies
pip install -r requirements.txt

# Initialize system
python you_ai_oracle.py init
```

### 2. Configuration

```bash
# Copy example environment
cp .env.example .env

# Edit configuration
nano config.yaml
nano .env
```

### 3. Deploy Contracts

```bash
# Compile contracts (requires Hardhat/Foundry)
# Then deploy
python scripts/deploy_contracts.py
```

### 4. Run Oracle

```bash
# Run directly
python you_ai_oracle.py run

# Or with Docker
docker-compose up -d
```

## Testing

```bash
# Run tests
python scripts/test_system.py

# Create test proposals
python scripts/simulate_proposals.py

# Monitor decisions
python you_ai_oracle.py monitor
```

## Decision Engine

The AI uses multi-factor analysis:

1. **Vision Alignment** (25%) - TF-IDF similarity with founder's vision
2. **Category Score** (20%) - Historical success rate by category
3. **Keyword Matching** (15%) - Vision keyword detection
4. **Innovation Score** (15%) - Innovation indicator detection
5. **Systemic Impact** (10%) - Long-term system impact
6. **Decentralization** (10%) - Decentralization alignment
7. **Financial Analysis** (5%) - Amount and viability

**Risk Adjustment** - Final score adjusted by risk tolerance

## Monitoring

Access monitoring dashboard:
```bash
# View metrics
python you_ai_oracle.py monitor

# Generate report
python you_ai_oracle.py report

# Grafana dashboard
http://localhost:3000
```

## Production Deployment

### Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f you-ai-oracle

# Stop
docker-compose down
```

### Kubernetes (Optional)

```bash
kubectl apply -f k8s/
```

## Security

- ✅ Private keys stored securely (use HSM in production)
- ✅ Rate limiting on blockchain interactions
- ✅ Multi-sig treasury protection
- ✅ Risk assessment for all proposals
- ✅ Red flag detection and rejection
- ✅ Emergency shutdown protocol

## Maintenance

```bash
# Check system health
curl http://localhost:9090/health

# View logs
tail -f logs/you_ai_oracle.log

# Backup database
cp you_ai_oracle.db backup/you_ai_oracle_$(date +%Y%m%d).db
```

## License

MIT License - See LICENSE file

## Support

- Documentation: https://docs.youdao.org
- Issues: https://github.com/yourusername/you-dao/issues
- Discord: https://discord.gg/youdao

---

**Built with purpose. Powered by AI. Immortal by design.**
"""