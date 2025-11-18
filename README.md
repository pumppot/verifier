# PUMP POT - Reward Verification Script

This repository contains the official, standalone Python script to independently verify the results of any Pump Pot raffle cycle.

The script is designed to be deterministic. When run on a given data package, it will always produce the same set of winners, guaranteeing that the raffle outcomes are fair and reproducible.

## Requirements

-   Python 3.7+
-   `pandas` and `pyarrow` libraries

You can install the required libraries using pip:
```bash
pip install pandas pyarrow
```

## How to Verify a Raffle

**Step 1: Download the Data Package**

Go to the Pump Pot raffle page and open the "Full Raffle History". Each past cycle will have a "Download" button. Download the `.zip` package for the cycle you wish to verify.

**Step 2: Unzip the Package**

Unzip the downloaded file. This will create a folder containing the raffle data (e.g., `2025-11-12T10_30/`).

**Step 3: Run the Script**

From your terminal, run the `verify_cycle.py` script and provide the path to the unzipped folder you just created.

```bash
python verify_cycle.py /path/to/your/unzipped-folder/2025-11-12T10_30
```

## What to Expect

The script will load the data, re-run the deterministic winner selection logic, and print a detailed report of the winners it calculated. The output will look like this:

```
--- Running deterministic winner calculation... ---
  - Using deterministic seed from Solana block: 380951234
  - Seed (Blockhash): DUCKT8VSgk2BXkMhQfxKVYfikEZCQf4dZ4ioPdGdaVxMN

--- Verification Result: Calculated Winners ---
==================================================

🏆 Power Buyer:
  - Wallet:       SoAndSo...WalletAddress
  - Win Chance:   15.7241%
  - Metric Value: 5000.00
  - Winning TX:   ...

🏆 Lottery:
  - Wallet:       Another...WalletAddress
  - Win Chance:   0.1250%
  - Holdings:     150.00
  - Contenders:   800

==================================================
✅ Verification script finished successfully.
```

The winners and metrics in this report should match the winners announced on the Pump Pot website for that cycle.

### The Principle of Determinism

The script's randomness is seeded by the **blockhash** of a finalized Solana block, which is recorded at the exact end of the raffle cycle. This information is included in the data package's `metadata.json` file as `verification_seed` (the blockhash) and `verification_slot` (the block number).

By using a public, on-chain, and cryptographically unpredictable value as the seed, we ensure that the "random" selection process is fair and can be reproduced by anyone. You can use any public Solana block explorer to look up the `verification_slot` and confirm that its `blockhash` matches the one used by the script.