---
name: ethereum-smart-contract-dev
description: "Ethereum Smart Contract Development — Foundry, Hardhat, ethers.js v6, viem, wagmi, Scaffold-ETH 2. Complete toolchain for Solidity dApp development"
version: 1.0.0
author: Hermes Agent (adapted from CryptoSkills.dev dev tools collection)
tags: [ethereum, solidity, smart-contracts, foundry, hardhat, dapp]
---

# Ethereum Smart Contract Development

Complete toolchain for Solidity development, testing, and deployment.

## Compilation & Testing

### Foundry (forge/cast/anvil/chisel)
```bash
# Install
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Init project
forge init my-project
cd my-project

# Build
forge build

# Test (unit + fuzz + invariant)
forge test
forge test --fuzz-runs 10000
forge test --invariant

# Deploy
forge create --rpc-url $RPC --private-key $PK src/MyContract.sol:MyContract

# Cast (CLI for onchain)
cast balance 0x... --rpc-url $RPC
cast send 0x... "transfer(address,uint256)" 0x... 100

# Anvil (local node)
anvil

# Chisel (REPL)
chisel
```

### Hardhat
```bash
npm init -y
npm i --save-dev hardhat
npx hardhat init

# Compile
npx hardhat compile

# Test (Mocha/Chai)
npx hardhat test

# Deploy (Ignition)
npx hardhat ignition deploy ./ignition/modules/MyModule.ts

# Fork mainnet
npx hardhat node --fork https://eth-mainnet.g.alchemy.com/v2/$KEY
```

## TypeScript Libraries

### ethers.js v6
```typescript
import { ethers } from "ethers";

const provider = new ethers.JsonRpcProvider(RPC_URL);
const signer = new ethers.Wallet(PRIVATE_KEY, provider);
const contract = new ethers.Contract(ADDRESS, ABI, signer);

// Read
const totalSupply = await contract.totalSupply();

// Write
const tx = await contract.transfer(to, amount);
await tx.wait();
```

### viem (type-safe, modern)
```typescript
import { createPublicClient, http, createWalletClient } from "viem";
import { mainnet } from "viem/chains";

const publicClient = createPublicClient({
  chain: mainnet, transport: http()
});
const balance = await publicClient.getBalance({ address: "0x..." });
```

### wagmi (React hooks)
```typescript
import { useReadContract, useWriteContract } from "wagmi";

const { data } = useReadContract({ abi, address, functionName: "balanceOf", args: [addr] });
const { writeContract } = useWriteContract();
```

## Full-Stack dApps

### Scaffold-ETH 2
```bash
npx create-eth@latest
# React hooks, contract hot reload, three-phase build (contract → deploy → frontend)
```

## EVM Testing Approaches
- **Unit tests**: `forge test` / `npx hardhat test`
- **Fuzz tests**: `forge test --fuzz-runs 5000`
- **Invariant tests**: `forge test --invariant`
- **Fork testing**: Test against mainnet state
- **Gas optimization**: `forge snapshot`

## Workflow
1. Choose framework: Foundry (faster) or Hardhat (richer plugin ecosystem)
2. Write contract in Solidity
3. Write tests (unit + fuzz)
4. Deploy (forge create / hardhat ignition)
5. Frontend integration (viem/wagmi + Scaffold-ETH)
