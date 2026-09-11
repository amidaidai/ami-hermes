---
name: crypto-security-audit-tools
description: "Crypto Security & Audit Tools — OpenZeppelin, Solidity security patterns, smart contract auditing, TRM Labs, GoPlus, Revoke.cash for onchain safety"
version: 1.0.0
author: Hermes Agent (adapted from CryptoSkills.dev security collection)
tags: [crypto, security, audit, solidity, smart-contract, auditing]
---

# Crypto Security & Audit Tools

Smart contract security auditing and onchain safety tools.

## Smart Contract Auditing

### OpenZeppelin
```bash
npm i @openzeppelin/contracts
```
- ERC20, ERC721, ERC1155 implementations
- Access control (Ownable, AccessControl)
- Upgradeable contracts (UUPS, Transparent)
- Security audits for each release

### Solidity Security Patterns
- Reentrancy guards
- Checks-Effects-Interactions pattern
- Pull over Push payments
- Emergency stop (circuit breaker)
- Rate limiting
- Signature replay protection (nonces, EIP-712)
- Oracle manipulation resistance (TWAP)

### Slither (Static Analysis)
```bash
pip install slither-analyzer
slither myContract.sol --print human-summary
slither myContract.sol --print contract-summary
```

## Onchain Security Tools

### GoPlus (Token Security)
- Token contract security audits
- Rug pull detection, honeypot checks
- API: docs.gopluslabs.io

### Revoke.cash
- Token approval management
- Revoke suspicious approvals
- Web: revoke.cash

### TRM Labs
- Blockchain intelligence
- Wallet screening, AML compliance
- API: trmlabs.com

## Audit Checklist

### Pre-Audit
- [ ] Use latest Solidity version (0.8.x)
- [ ] No `tx.origin` for auth (use `msg.sender`)
- [ ] No unchecked external calls
- [ ] Use OpenZeppelin's ReentrancyGuard
- [ ] Events emitted on state changes

### Code Review
- [ ] Arithmetic safety (use Solidity 0.8+ built-in overflow check)
- [ ] Access control on all admin functions
- [ ] Front-running resistance (commit-reveal, FCFS limits)
- [ ] Oracle manipulation resistance
- [ ] Flash loan attack vectors
- [ ] Upgradeability risks (storage collision)

### Post-Deploy
- [ ] Verify contract on Etherscan
- [ ] Set up monitoring (Tenderly, Forta)
- [ ] Timelock on admin functions
- [ ] Emergency pause mechanism
- [ ] Bug bounty program

## Workflow
1. Write contract with OpenZeppelin templates
2. Run Slither static analysis
3. Manual review against checklist
4. Professional audit for production
5. Post-deploy monitoring
