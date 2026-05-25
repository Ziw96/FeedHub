#!/bin/bash
# Run this on your Mac to migrate the URA scraper from FeedHub to pp-pecari.
# Prerequisites: gh CLI authenticated, or git push access to Ziw96/pp-pecari.
set -euo pipefail

DEST_DIR="$HOME/Code/pp-pecari"  # Change to your preferred location

echo "==> Cloning pp-pecari..."
git clone git@github.com:Ziw96/pp-pecari.git "$DEST_DIR"
cd "$DEST_DIR"

echo "==> Fetching scraper code from FeedHub branch..."
git remote add feedhub git@github.com:Ziw96/FeedHub.git
git fetch feedhub claude/ura-property-scraper-IlwNO

echo "==> Importing files (clean copy, no FeedHub history)..."
git archive feedhub/claude/ura-property-scraper-IlwNO -- \
    .gitignore README.md requirements.txt ura_scraper/ tests/ | tar -x

# Remove FeedHub's LICENSE if pp-pecari already has one (or keep it)
# rm -f LICENSE

echo "==> Committing..."
git add -A
git commit -m "Initial import: URA apartment/condo resale scraper

Dual-source CLI (--source api|html) for pulling private residential
resale transactions from URA Singapore.

Migrated from Ziw96/FeedHub branch claude/ura-property-scraper-IlwNO."

echo "==> Pushing to pp-pecari main..."
git push -u origin main

echo ""
echo "Done! To get started:"
echo "  cd $DEST_DIR"
echo "  pip install -r requirements.txt"
echo "  export URA_ACCESS_KEY='your-key'"
echo "  python -m ura_scraper sync"

echo ""
echo "==> Cleaning up FeedHub remote..."
git remote remove feedhub
