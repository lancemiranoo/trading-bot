"""
Upload trades from CSV to Firebase Firestore.

Usage:
    python upload_trades.py                           # Upload all trades
    python upload_trades.py --file logs/trades.csv    # Specify CSV path
    python upload_trades.py --dry-run                 # Preview without uploading
"""

import csv
import os
import sys
import argparse
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore


def init_firestore():
    """Initialize Firebase Admin SDK with service account credentials."""
    cred_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")

    if not os.path.exists(cred_path):
        print(f"ERROR: Service account key not found at: {cred_path}")
        print()
        print("To get your service account key:")
        print("  1. Go to Firebase Console -> Project Settings -> Service Accounts")
        print("  2. Click 'Generate new private key'")
        print("  3. Save the JSON file as 'serviceAccountKey.json' in this directory")
        sys.exit(1)

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    return firestore.client()


def parse_csv(file_path):
    """Parse trades.csv and return a list of trade dictionaries."""
    trades = []

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Skip empty rows
            if not row.get("Ticket", "").strip():
                continue

            # Parse timestamp: "26/05/2026 0:25" -> datetime
            timestamp_str = row["Timestamp"].strip()
            timestamp = datetime.strptime(timestamp_str, "%d/%m/%Y %H:%M")

            # Parse status into result (WIN/LOSS) and clean status
            status_raw = row["Status"].strip()
            if "WIN" in status_raw:
                result = "WIN"
            elif "LOSS" in status_raw:
                result = "LOSS"
            else:
                result = "UNKNOWN"

            trade = {
                "timestamp": timestamp,
                "ticket": row["Ticket"].strip(),
                "symbol": row["Symbol"].strip(),
                "type": row["Type"].strip(),
                "status": status_raw,
                "result": result,
                "price": float(row["Price"].strip()),
                "sl": float(row["SL"].strip()),
                "tp": float(row["TP"].strip()),
                "profit": float(row["Profit"].strip()),
                "loss": float(row["Loss"].strip()),
                "channel": row["Channel"].strip(),
                "uploadedAt": firestore.SERVER_TIMESTAMP,
            }

            trades.append(trade)

    return trades


def upload_trades(db, trades, dry_run=False):
    """Batch-write trades to Firestore 'trades' collection."""
    if dry_run:
        print(f"\n[DRY RUN] Would upload {len(trades)} trades:\n")
        for t in trades:
            print(f"  {t['timestamp']} | {t['ticket']} | {t['symbol']} "
                  f"| {t['type']} | {t['result']} | P:{t['profit']} L:{t['loss']} "
                  f"| {t['channel']}")
        return 0, 0

    uploaded = 0
    skipped = 0
    collection = db.collection("trades")

    # Firestore batch limit is 500 writes per batch
    batch_size = 500
    batch = db.batch()
    batch_count = 0

    for trade in trades:
        ticket = trade["ticket"]

        # Check for duplicate by ticket number
        existing = collection.where("ticket", "==", ticket).limit(1).get()
        if existing:
            print(f"  SKIP (duplicate): Ticket {ticket}")
            skipped += 1
            continue

        # Use ticket as document ID for easy lookup
        doc_ref = collection.document(ticket)
        batch.set(doc_ref, trade)
        batch_count += 1
        uploaded += 1

        # Commit batch when it reaches the limit
        if batch_count >= batch_size:
            batch.commit()
            print(f"  Committed batch of {batch_count} trades")
            batch = db.batch()
            batch_count = 0

    # Commit remaining trades
    if batch_count > 0:
        batch.commit()
        print(f"  Committed final batch of {batch_count} trades")

    return uploaded, skipped


def main():
    parser = argparse.ArgumentParser(description="Upload trades CSV to Firestore")
    parser.add_argument(
        "--file",
        default=os.path.join(os.path.dirname(__file__), "logs", "trades.csv"),
        help="Path to the trades CSV file (default: logs/trades.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview trades without uploading to Firestore",
    )
    args = parser.parse_args()

    # Validate CSV file exists
    if not os.path.exists(args.file):
        print(f"ERROR: CSV file not found: {args.file}")
        sys.exit(1)

    print(f"Reading trades from: {args.file}")
    trades = parse_csv(args.file)
    print(f"Found {len(trades)} trades in CSV")

    if not trades:
        print("No trades to upload.")
        return

    if args.dry_run:
        # Dry run doesn't need Firestore connection
        # But we need SERVER_TIMESTAMP replaced for display
        for t in trades:
            t.pop("uploadedAt", None)
        upload_trades(None, trades, dry_run=True)
    else:
        print("\nConnecting to Firestore...")
        db = init_firestore()
        print("Connected!\n")

        uploaded, skipped = upload_trades(db, trades)
        print(f"\nDone! Uploaded: {uploaded} | Skipped (duplicates): {skipped}")


if __name__ == "__main__":
    main()
