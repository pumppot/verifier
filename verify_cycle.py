# PUMP POT - STANDALONE REWARD VERIFICATION SCRIPT
#
# Description:
#   This script verifies the results of a Pump Pot reward cycle using a
#   self-contained data package. It recalculates the winners deterministically
#   based only on the data and rules within the package and prints the result.
#   It performs no network, database, or other external file operations.
#
# Requirements:
#   - Python 3.7+
#   - pandas
#   - pyarrow
#   (Install with: pip install pandas pyarrow)
#
# Usage:
#   1. Download and unzip a verification package (e.g., '2025-10-28T14_30.zip').
#   2. Run the script from your terminal, pointing it to the unzipped directory:
#      python verify_cycle.py /path/to/2025-10-28T14_30
#
import argparse
import os
import sys
import json
import pandas as pd
import random
from typing import Dict, List, Tuple, Optional

# --- CORE CALCULATION LOGIC ---

def _weighted_choice(participants: List[Tuple[str, float]]) -> Optional[str]:
    if not participants: return None
    total_weight = sum(weight for item, weight in participants)
    if total_weight == 0:
        if participants:
            return random.choice([item for item, weight in participants])
        return None
    r = random.uniform(0, total_weight)
    upto = 0
    for item, weight in participants:
        if upto + weight >= r:
            return item
        upto += weight
    return participants[-1][0] if participants else None

def calculate_all_rewards_from_package(
    token_holders: List[Dict],
    cycle_stats_snapshot: Dict,
    initial_balances_snapshot: Dict,
    verification_seed: str,
    rules: Dict
) -> Dict:
    """
    Standalone version of the reward calculation logic.
    """
    random.seed(verification_seed)

    final_balances = {h["address"]: h["amount"] for h in token_holders}
    universally_eligible_wallets = {
        w for w, b in final_balances.items()
        if w != '_start_signature' and b >= rules['min_eligible_holding_amount']
    }

    # --- Power Buyer ---
    power_buyer_participants = sorted(
        [(w, s["largest_buy"]) for w, s in cycle_stats_snapshot.items() if w in universally_eligible_wallets and s["largest_buy"] > 0],
        key=lambda item: item[0]
    )
    power_buyer_winner_wallet = _weighted_choice(power_buyer_participants)

    # --- Volume King ---
    volume_king_participants = sorted(
        [(w, s["total_volume"]) for w, s in cycle_stats_snapshot.items() if w in universally_eligible_wallets and s["total_volume"] >= rules['min_trade_volume']],
        key=lambda item: item[0]
    )
    volume_king_winner_wallet = _weighted_choice(volume_king_participants)

    # --- Active Holder ---
    active_holder_participants_unsorted = []
    for wallet in universally_eligible_wallets:
        final_balance = final_balances.get(wallet, 0.0)
        start_balance = initial_balances_snapshot.get(wallet, 0.0)
        net_change = final_balance - start_balance
        if net_change >= 0:
            weight = (1.0 * net_change) + (0.25 * start_balance)
            if weight > 0: active_holder_participants_unsorted.append((wallet, weight))
    active_holder_participants = sorted(active_holder_participants_unsorted, key=lambda item: item[0])
    active_holder_winner_wallet = _weighted_choice(active_holder_participants)

    # --- Lottery ---
    lottery_participants = sorted(list(universally_eligible_wallets))
    lottery_winner_wallet = random.choice(lottery_participants) if lottery_participants else None

    # --- Assemble Results ---
    results = {}
    if power_buyer_winner_wallet:
        total_weight = sum(w for _, w in power_buyer_participants)
        winner_weight = cycle_stats_snapshot[power_buyer_winner_wallet]['largest_buy']
        win_chance = (winner_weight / total_weight) * 100 if total_weight > 0 else 100.0
        results["power_buyer"] = {"wallet": power_buyer_winner_wallet, "metric": winner_weight, "tx_signature": cycle_stats_snapshot[power_buyer_winner_wallet]['largest_buy_tx'], "win_chance_percent": win_chance}
    else: results["power_buyer"] = None

    if volume_king_winner_wallet:
        total_weight = sum(w for _, w in volume_king_participants)
        winner_weight = cycle_stats_snapshot[volume_king_winner_wallet]['total_volume']
        win_chance = (winner_weight / total_weight) * 100 if total_weight > 0 else 100.0
        results["volume_king"] = {"wallet": volume_king_winner_wallet, "metric": winner_weight, "buys": cycle_stats_snapshot[volume_king_winner_wallet]['buys'], "sells": cycle_stats_snapshot[volume_king_winner_wallet]['sells'], "win_chance_percent": win_chance}
    else: results["volume_king"] = None

    if active_holder_winner_wallet:
        total_weight = sum(w for _, w in active_holder_participants)
        winner_weight = next((w for wallet, w in active_holder_participants if wallet == active_holder_winner_wallet), 0.0)
        win_chance = (winner_weight / total_weight) * 100 if total_weight > 0 else 100.0
        winner_final_balance = final_balances.get(active_holder_winner_wallet, 0)
        winner_start_balance = initial_balances_snapshot.get(active_holder_winner_wallet, 0)
        results["active_holder"] = {"wallet": active_holder_winner_wallet, "metric": winner_final_balance, "final_balance": winner_final_balance, "start_balance": winner_start_balance, "win_chance_percent": win_chance}
    else: results["active_holder"] = None

    if lottery_winner_wallet:
        total_participants = len(lottery_participants)
        win_chance = (1 / total_participants) * 100 if total_participants > 0 else 100.0
        results["lottery"] = {"wallet": lottery_winner_wallet, "metric": final_balances.get(lottery_winner_wallet, 0), "win_chance_percent": win_chance}
    else: results["lottery"] = None
    return results

# --- SCRIPT MAIN LOGIC ---

def load_verification_package(directory: str) -> Dict:
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"Verification directory not found: {directory}")
    print(f"--- Loading Verification Package from '{os.path.basename(directory)}' ---")
    files = {"metadata": os.path.join(directory, "metadata.json"), "initial_balances": os.path.join(directory, "initial_balances.parquet"), "processed_swaps": os.path.join(directory, "processed_swaps.parquet"), "final_balances": os.path.join(directory, "final_balances.parquet")}
    for name, path in files.items():
        if not os.path.exists(path): raise FileNotFoundError(f"Missing required file in package: {os.path.basename(path)}")
    with open(files["metadata"], 'r') as f: metadata = json.load(f)
    initial_df = pd.read_parquet(files["initial_balances"])
    swaps_df = pd.read_parquet(files["processed_swaps"])
    final_df = pd.read_parquet(files["final_balances"])
    print("  - Successfully loaded all data files and metadata.")
    return {"metadata": metadata, "initial_balances_df": initial_df, "processed_swaps_df": swaps_df, "final_balances_df": final_df}

def prepare_data_for_calculation(package: Dict) -> Dict:
    initial_balances_snapshot = {row['wallet']: row['amount'] for _, row in package["initial_balances_df"].iterrows()}
    initial_balances_snapshot['_start_signature'] = package["metadata"].get("start_signature")
    cycle_stats_snapshot = {row['wallet']: row.to_dict() for _, row in package["processed_swaps_df"].iterrows()}
    token_holders = package["final_balances_df"].rename(columns={'wallet': 'address'}).to_dict('records')
    print("\n--- Data prepared for recalculation ---")
    print(f"  - Initial Holders: {len(initial_balances_snapshot) - 1}")
    print(f"  - Traders This Cycle: {len(cycle_stats_snapshot)}")
    print(f"  - Final Holders: {len(token_holders)}")
    return {"token_holders": token_holders, "cycle_stats_snapshot": cycle_stats_snapshot, "initial_balances_snapshot": initial_balances_snapshot}

def print_winner_report(winners: Dict):
    """Prints a clear, formatted report of the calculated winners."""
    print("\n--- Verification Result: Calculated Winners ---")
    print("=" * 50)
    for category, winner_data in winners.items():
        category_title = category.replace('_', ' ').title()
        print(f"\n🏆 {category_title}:")
        if winner_data:
            print(f"  - Wallet:       {winner_data['wallet']}")
            # Display win chance for all categories
            if 'win_chance_percent' in winner_data:
                print(f"  - Win Chance:   {winner_data['win_chance_percent']:.4f}%")
            # Category-specific details
            if category == 'active_holder':
                 print(f"  - Holdings:     {winner_data.get('final_balance', 0):.2f} (Started with {winner_data.get('start_balance', 0):.2f})")
            elif 'metric' in winner_data:
                print(f"  - Metric Value: {winner_data['metric']:.2f}")
            if 'tx_signature' in winner_data and winner_data['tx_signature']:
                print(f"  - Winning TX:   {winner_data['tx_signature']}")
            if 'buys' in winner_data:
                print(f"  - Breakdown:    Buys={winner_data['buys']:.2f}, Sells={winner_data['sells']:.2f}")
        else:
            print("  - No eligible winner was found for this category.")
    print("\n" + "=" * 50)
    print("✅ Verification script finished successfully.")
    print("This result is deterministic. Running the script on the same package will always yield the same winners.")

def main():
    parser = argparse.ArgumentParser(description="Verifies the results of a Pump Pot reward cycle.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("packagedir", help="Path to the unzipped verification package directory.")
    args = parser.parse_args()
    try:
        package = load_verification_package(args.packagedir)
        calculation_inputs = prepare_data_for_calculation(package)
        print("\n--- Running deterministic winner calculation... ---")
        verified_winners = calculate_all_rewards_from_package(
            token_holders=calculation_inputs["token_holders"],
            cycle_stats_snapshot=calculation_inputs["cycle_stats_snapshot"],
            initial_balances_snapshot=calculation_inputs["initial_balances_snapshot"],
            verification_seed=package["metadata"]["verification_seed"],
            rules=package["metadata"]["rules"]
        )
        print_winner_report(verified_winners)
    except (FileNotFoundError, KeyError, Exception) as e:
        print(f"\n❌ ERROR: Could not process verification package. Reason: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()