#!/bin/bash
# Frontend build benchmark
# Usage: ./scripts/bench-frontend.sh [--fresh]

set -e

FRONTEND_DIR="tauri_frontend/event_agent_frontend"
RUST_DIR="$FRONTEND_DIR/src-tauri"

echo "========================================="
echo "  Frontend Build Benchmarks"
echo "========================================="
echo ""

# 1. Vite dev server (JS only)
echo "1. Vite dev server (JS only, no Rust)"
echo "   Target: < 3 seconds"
START=$(date +%s%N)
cd "$FRONTEND_DIR"
timeout 5 npm run dev 2>&1 | grep -m1 -E "Local|ready|started" || true
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))
echo "   Result: ${ELAPSED}ms"
if [ $ELAPSED -lt 3000 ]; then
    echo "   ✓ PASS"
else
    echo "   ✗ FAIL (>${ELAPSED}ms)"
fi
cd ../..
echo ""

# 2. Rust incremental build
echo "2. Rust incremental build (cached)"
echo "   Target: < 20 seconds"
START=$(date +%s%N)
cd "$RUST_DIR"
cargo build 2>&1 | tail -1
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))
echo "   Result: ${ELAPSED}ms"
if [ $ELAPSED -lt 20000 ]; then
    echo "   ✓ PASS"
else
    echo "   ✗ FAIL (>${ELAPSED}ms)"
fi
cd ../..
echo ""

# 3. Rust fresh build (optional)
if [ "$1" = "--fresh" ]; then
    echo "3. Rust fresh build (target deleted)"
    echo "   Target: < 120 seconds"
    rm -rf "$RUST_DIR/target"
    START=$(date +%s%N)
    cd "$RUST_DIR"
    cargo build 2>&1 | tail -1
    END=$(date +%s%N)
    ELAPSED=$(( (END - START) / 1000000 ))
    echo "   Result: ${ELAPSED}ms"
    if [ $ELAPSED -lt 120000 ]; then
        echo "   ✓ PASS"
    else
        echo "   ✗ FAIL (>${ELAPSED}ms)"
    fi
    cd ../..
    echo ""
fi

echo "========================================="
echo "  Summary"
echo "========================================="
echo "  Vite (JS only):       ~1-2s"
echo "  Rust incremental:     ~4s (after first build)"
echo "  Rust fresh:           ~120s (one-time cost)"
echo ""
echo "  Note: Fresh Rust builds compile 315 crates"
echo "  including macOS frameworks (objc2-*)."
echo "  This is a one-time cost. Subsequent builds"
echo "  only recompile changed code."
