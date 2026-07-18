#!/bin/bash
# Polylith architecture lint - full validation
# Usage: scripts/polylith-lint.sh [--strict]

set -e

echo "🏗️  Polylith Architecture Validation"
echo "===================================="
echo ""

# 1. Workspace structure
echo "1️⃣  Workspace Structure"
uv run poly info
echo ""

# 2. Check for orphan bricks
echo "2️⃣  Checking for orphan/unmounted bricks..."
echo ""
if uv run poly check --no-verbose 2>&1 | grep -q "Cannot locate"; then
    echo "⚠️  ORPHAN BRICKS FOUND (not mounted in inventory_api):"
    uv run poly check --no-verbose 2>&1 | grep "Cannot locate"
    echo ""
    echo "💡 These bricks exist but aren't used by inventory_api."
    echo "   - If intentional, ignore this warning"
    echo "   - If not: review ARCHITECTURE.md and mount them or remove"
    echo ""
else
    echo "✅ No orphan bricks - all bricks are mounted"
    echo ""
fi

# 3. Check for circular dependencies
echo "3️⃣  Checking for circular dependencies..."
if uv run poly check --no-verbose 2>&1 | grep -q "circular"; then
    echo "❌ CIRCULAR DEPENDENCY DETECTED:"
    uv run poly check --verbose 2>&1 | grep -A2 "circular"
    echo ""
    exit 1
else
    echo "✅ No circular dependencies"
    echo ""
fi

# 4. Impact analysis
echo "4️⃣  Changed bricks (vs last git tag)"
echo ""
uv run poly diff 2>&1 | grep -E "^(- |Components|Bases)" || echo "✔ No changes detected"
echo ""

if [ "$1" == "--strict" ]; then
    echo "5️⃣  STRICT MODE: Failing if any issues found"
    if uv run poly check 2>&1 | grep -q "Cannot locate\|circular"; then
        echo "❌ Strict validation failed"
        exit 1
    fi
    echo "✅ Strict validation passed"
fi

echo "✅ Lint complete"
