#!/bin/bash
#
# RF Model v2.0 Deployment Script
#
# This script automates the deployment process for the Random Forest recommender.
#
# Usage:
#   ./scripts/deploy_rf_model.sh [stage]
#
# Stages:
#   export    - Export model from notebook
#   test      - Run unit and integration tests
#   deploy    - Deploy to production with A/B testing
#   rollout   - Update traffic split
#   rollback  - Rollback to legacy model
#   status    - Check deployment status

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_dependencies() {
    log_info "Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.10+"
        exit 1
    fi

    # Check required Python packages
    python3 -c "import joblib, sklearn, pandas, numpy" 2>/dev/null || {
        log_error "Required Python packages not found. Run: pip install -r backend/requirements.txt"
        exit 1
    }

    # Check if backend is running
    if ! curl -s http://localhost:8000/health > /dev/null; then
        log_warning "Backend not running. Some commands may fail."
    fi

    log_success "Dependencies check passed"
}

export_model() {
    log_info "Exporting RF model from notebook..."

    # Check if notebook has been run
    MODEL_FILE="ml/notebook/../models/improved_rf/improved_rf_topk_model.pkl"
    if [ ! -f "$MODEL_FILE" ]; then
        log_error "Model not found at $MODEL_FILE"
        log_error "Please run ml/notebook/improved_rf_topk.ipynb first!"
        exit 1
    fi

    # Run export script
    cd ml/scripts
    python3 export_rf_model.py

    if [ $? -eq 0 ]; then
        log_success "Model exported successfully"
        log_info "Model location: backend/app/ml/models/rf_v2/rf_recommender.pkl"
    else
        log_error "Model export failed"
        exit 1
    fi

    cd "$PROJECT_ROOT"
}

run_tests() {
    log_info "Running tests..."

    # Unit tests
    log_info "Running unit tests..."
    cd backend

    if pytest tests/ -v --cov=app/ml --cov-report=term-missing; then
        log_success "Unit tests passed"
    else
        log_error "Unit tests failed"
        exit 1
    fi

    # Integration tests
    log_info "Running integration tests..."
    if pytest tests/integration/test_rf_recommender.py -v; then
        log_success "Integration tests passed"
    else
        log_warning "Integration tests failed (might be expected if backend not running)"
    fi

    cd "$PROJECT_ROOT"
}

deploy_model() {
    log_info "Deploying RF model to production..."

    # Check if model exists
    if [ ! -f "backend/app/ml/models/rf_v2/rf_recommender.pkl" ]; then
        log_error "Model not found. Run './scripts/deploy_rf_model.sh export' first"
        exit 1
    fi

    # Restart backend to load new model
    log_info "Restarting backend service..."
    if docker compose -f compose.dev.yaml restart backend; then
        log_success "Backend restarted"
    else
        log_warning "Failed to restart backend (might not be in Docker)"
    fi

    # Wait for backend to be ready
    log_info "Waiting for backend to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null; then
            log_success "Backend is ready"
            break
        fi
        sleep 1
    done

    # Test new endpoint
    log_info "Testing RF recommender endpoint..."
    if curl -s http://localhost:8000/api/v1/recommend/v2/model-info > /dev/null; then
        log_success "RF endpoint is working"
    else
        log_error "RF endpoint test failed"
        exit 1
    fi

    log_success "Deployment completed successfully"
    log_info "Next step: Start A/B testing with './scripts/deploy_rf_model.sh rollout 0.1'"
}

update_rollout() {
    TRAFFIC_SPLIT=$1

    if [ -z "$TRAFFIC_SPLIT" ]; then
        log_error "Usage: ./scripts/deploy_rf_model.sh rollout <traffic_split>"
        log_info "Example: ./scripts/deploy_rf_model.sh rollout 0.1  # 10% to RF"
        exit 1
    fi

    log_info "Updating traffic split to $TRAFFIC_SPLIT..."

    # Get admin token (you'll need to implement actual auth)
    # For now, using placeholder
    ADMIN_TOKEN="your-admin-token-here"

    RESPONSE=$(curl -s -X POST \
        "http://localhost:8000/api/v1/recommend/v2/rollout?traffic_split=$TRAFFIC_SPLIT" \
        -H "Authorization: Bearer $ADMIN_TOKEN")

    if echo "$RESPONSE" | grep -q "success"; then
        log_success "Traffic split updated to ${TRAFFIC_SPLIT}%"
        log_info "RF model: $(echo "$RESPONSE" | jq -r .rf_percentage)"
        log_info "Legacy model: $(echo "$RESPONSE" | jq -r .legacy_percentage)"
    else
        log_error "Failed to update traffic split"
        echo "$RESPONSE"
        exit 1
    fi
}

rollback_model() {
    log_warning "Rolling back to legacy model..."

    # Set traffic to 0% (all legacy)
    ADMIN_TOKEN="your-admin-token-here"

    RESPONSE=$(curl -s -X POST \
        "http://localhost:8000/api/v1/recommend/v2/rollout?traffic_split=0.0" \
        -H "Authorization: Bearer $ADMIN_TOKEN")

    if echo "$RESPONSE" | grep -q "success"; then
        log_success "Rollback completed. All traffic using legacy model."
    else
        log_error "Rollback failed"
        echo "$RESPONSE"
        exit 1
    fi
}

check_status() {
    log_info "Checking deployment status..."

    # Check backend health
    log_info "Backend health:"
    curl -s http://localhost:8000/health | jq .

    # Check model info
    log_info "Model information:"
    curl -s http://localhost:8000/api/v1/recommend/v2/model-info | jq .

    # Check A/B metrics (requires admin token)
    log_info "A/B test metrics:"
    ADMIN_TOKEN="your-admin-token-here"
    curl -s http://localhost:8000/api/v1/recommend/v2/ab-metrics \
        -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
}

show_help() {
    echo "RF Model v2.0 Deployment Script"
    echo ""
    echo "Usage: ./scripts/deploy_rf_model.sh [command]"
    echo ""
    echo "Commands:"
    echo "  export        Export model from notebook to production format"
    echo "  test          Run unit and integration tests"
    echo "  deploy        Deploy model to production (start with 0% traffic)"
    echo "  rollout <pct> Update traffic split (e.g., rollout 0.1 for 10%)"
    echo "  rollback      Rollback to legacy model (set traffic to 0%)"
    echo "  status        Check deployment status and metrics"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Full deployment workflow"
    echo "  ./scripts/deploy_rf_model.sh export    # Export model"
    echo "  ./scripts/deploy_rf_model.sh test      # Run tests"
    echo "  ./scripts/deploy_rf_model.sh deploy    # Deploy with 0% traffic"
    echo "  ./scripts/deploy_rf_model.sh rollout 0.1  # Start with 10%"
    echo "  ./scripts/deploy_rf_model.sh rollout 0.5  # Increase to 50%"
    echo "  ./scripts/deploy_rf_model.sh rollout 1.0  # Full migration"
    echo ""
    echo "  # Emergency rollback"
    echo "  ./scripts/deploy_rf_model.sh rollback"
    echo ""
    echo "  # Check status"
    echo "  ./scripts/deploy_rf_model.sh status"
}

# Main script
COMMAND=${1:-help}

case "$COMMAND" in
    export)
        check_dependencies
        export_model
        ;;
    test)
        check_dependencies
        run_tests
        ;;
    deploy)
        check_dependencies
        deploy_model
        ;;
    rollout)
        check_dependencies
        update_rollout "$2"
        ;;
    rollback)
        rollback_model
        ;;
    status)
        check_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
