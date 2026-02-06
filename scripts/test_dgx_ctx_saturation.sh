#!/bin/bash
# Script d'aide pour exécuter les tests de saturation du contexte sur DGX Spark
#
# Usage:
#   ./scripts/test_dgx_ctx_saturation.sh [before|after|all|json]
#
# Arguments:
#   before  - Test démonstration du problème (AVANT fix)
#   after   - Test validation du fix (APRÈS fix)
#   json    - Test stabilité génération JSON
#   all     - Tous les tests (suite complète)
#
# Exemples:
#   ./scripts/test_dgx_ctx_saturation.sh before
#   ./scripts/test_dgx_ctx_saturation.sh after
#   ./scripts/test_dgx_ctx_saturation.sh all

set -e

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DGX_HOSTNAME=${DGX_HOSTNAME:-gx10-957b}
DGX_IP=${DGX_IP:-100.107.87.123}
TEST_FILE="integration_tests/test_llama_cpp_context_saturation.py"
TEST_CLASS="TestLlamaCppContextSaturation"

# Fonction d'aide
print_usage() {
    echo "Usage: $0 [before|after|all|json]"
    echo ""
    echo "Arguments:"
    echo "  before  - Test démonstration du problème (AVANT fix)"
    echo "  after   - Test validation du fix (APRÈS fix)"
    echo "  json    - Test stabilité génération JSON"
    echo "  all     - Tous les tests (suite complète)"
    echo ""
    echo "Exemples:"
    echo "  $0 before"
    echo "  $0 after"
    echo "  $0 all"
    exit 1
}

# Vérification des prérequis
check_prerequisites() {
    echo -e "${BLUE}[CHECK]${NC} Vérification des prérequis..."
    
    # Vérifier connexion Tailscale
    if ! command -v tailscale &> /dev/null; then
        echo -e "${YELLOW}[WARN]${NC} Tailscale CLI non trouvé (optionnel si VPN actif)"
    else
        if tailscale status | grep -q "$DGX_HOSTNAME"; then
            echo -e "${GREEN}[OK]${NC} Connexion Tailscale VPN active ($DGX_HOSTNAME)"
        else
            echo -e "${YELLOW}[WARN]${NC} DGX non trouvé dans Tailscale status"
            echo -e "${YELLOW}[WARN]${NC} Assurez-vous que le VPN est actif"
        fi
    fi
    
    # Vérifier connectivité HTTP (optionnel)
    if command -v curl &> /dev/null; then
        if curl -s --connect-timeout 5 "http://${DGX_HOSTNAME}:8002/health" &> /dev/null || \
           curl -s --connect-timeout 5 "http://${DGX_IP}:8002/health" &> /dev/null; then
            echo -e "${GREEN}[OK]${NC} Service llm-instruct accessible"
        else
            echo -e "${YELLOW}[WARN]${NC} Service llm-instruct non accessible (les tests seront skippés)"
        fi
    fi
    
    echo ""
}

# Fonction pour exécuter un test spécifique
run_test() {
    local test_name=$1
    local description=$2
    
    echo -e "${BLUE}[TEST]${NC} ${description}"
    echo -e "${BLUE}======${NC} $test_name"
    echo ""
    
    poetry run pytest "${TEST_FILE}::${TEST_CLASS}::${test_name}" -v -s --tb=short
    
    local exit_code=$?
    echo ""
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}[PASS]${NC} ${test_name}"
    else
        echo -e "${RED}[FAIL]${NC} ${test_name}"
    fi
    
    echo ""
    return $exit_code
}

# Parse argument
MODE=${1:-all}

case $MODE in
    before)
        check_prerequisites
        echo -e "${YELLOW}[MODE]${NC} Test AVANT fix (démonstration problème)"
        echo ""
        run_test "test_ctx_saturation_before_fix_instruct" \
                 "Démonstration troncature avec ctx-size 2048"
        ;;
    
    after)
        check_prerequisites
        echo -e "${YELLOW}[MODE]${NC} Test APRÈS fix (validation correction)"
        echo ""
        run_test "test_ctx_saturation_after_fix_instruct" \
                 "Validation absence troncature avec ctx-size 4096"
        ;;
    
    json)
        check_prerequisites
        echo -e "${YELLOW}[MODE]${NC} Test stabilité JSON"
        echo ""
        run_test "test_json_generation_stability_instruct" \
                 "Validation génération JSON complète"
        ;;
    
    all)
        check_prerequisites
        echo -e "${YELLOW}[MODE]${NC} Suite complète de tests"
        echo ""
        
        # Exécuter tous les tests avec marqueur dgx
        poetry run pytest -m dgx -v -s --tb=short
        
        exit_code=$?
        echo ""
        
        if [ $exit_code -eq 0 ]; then
            echo -e "${GREEN}[SUCCESS]${NC} Tous les tests DGX passent"
        else
            echo -e "${RED}[FAILURE]${NC} Certains tests ont échoué"
        fi
        
        exit $exit_code
        ;;
    
    *)
        echo -e "${RED}[ERROR]${NC} Argument invalide: $MODE"
        echo ""
        print_usage
        ;;
esac
