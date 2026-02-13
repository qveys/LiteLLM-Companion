"""
Test suite for Story 5 Deep Dive Review: CLI Detection System Analysis

This test suite validates the comprehensive technical review of the CLI detection
system, ensuring all analysis, recommendations, and implementation examples
are properly documented and actionable.
"""

from pathlib import Path

import pytest


class TestStory5DeepDiveReview:
    """Test class for Story 5 deep dive review content validation."""

    @pytest.fixture
    def deep_dive_content(self) -> str:
        """Load the Story 5 deep dive review content."""
        review_path = Path("reviews/story-5-deep-dive-review.md")
        assert review_path.exists(), f"Review file not found: {review_path}"
        return review_path.read_text()

    @pytest.fixture
    def deep_dive_lines(self, deep_dive_content) -> list[str]:
        """Return the review content as lines."""
        return deep_dive_content.split("\n")

    # ========================================================================
    # EXISTENCE AND STRUCTURE TESTS
    # ========================================================================

    def test_file_exists(self, deep_dive_content):
        """Test that the deep dive review file exists and has content."""
        assert len(deep_dive_content) > 1000, "Review should have substantial content"
        assert "Story 5 Deep Dive Review" in deep_dive_content

    def test_has_proper_sections(self, deep_dive_content):
        """Test that the review has all required sections."""
        required_sections = [
            "Contexte de la Review Complémentaire",
            "Analyse Approfondie des Composants",
            "Architecture du Système CLI",
            "Détection des Processus CLI",
            "Analyse de l'Historique Shell",
            "Détection WSL",
            "Tests de Validation Proposés",
            "Checklist d'Amélioration Priorisée",
            "Métriques de Qualité Proposées",
            "Conclusion et Recommandations Finales",
            "Annexes",
        ]

        for section in required_sections:
            assert section in deep_dive_content, f"Missing required section: {section}"

    def test_has_mermaid_diagram(self, deep_dive_content):
        """Test that the review includes architecture diagrams."""
        assert "```mermaid" in deep_dive_content, "Should have Mermaid diagram"
        assert "graph TD" in deep_dive_content, "Should have flow diagram"

    def test_has_code_examples(self, deep_dive_content):
        """Test that the review includes implementation code examples."""
        assert "```python" in deep_dive_content, "Should have Python code examples"

    def test_has_tables(self, deep_dive_content):
        """Test that the review includes data tables."""
        assert "| Shell | Format | Exemple | Défis |" in deep_dive_content, (
            "Should have shell format table"
        )
        assert (
            "| Métrique | Cible Actuelle | Cible Améliorée | Méthode de Mesure |"
            in deep_dive_content
        ), "Should have metrics table"

    # ========================================================================
    # ARCHITECTURE ANALYSIS TESTS
    # ========================================================================

    def test_identifies_architecture_components(self, deep_dive_content):
        """Test that the review identifies key architecture components."""
        components = [
            "Scan des processus",
            "Filtrage des processus AI",
            "Suivi d'état PID",
            "Calcul de la durée",
            "Estimation des coûts",
            "Export OpenTelemetry",
            "Analyse historique shell",
            "Persistance des offsets",
            "Comptage des commandes",
        ]

        for component in components:
            assert component in deep_dive_content, f"Missing architecture component: {component}"

    def test_identifies_strengths(self, deep_dive_content):
        """Test that the review identifies architecture strengths."""
        strengths = [
            "Détection en temps réel des processus CLI AI",
            "Suivi d'état persistant entre les scans",
            "Analyse incrémentale de l'historique shell",
            "Prise en charge multi-shell",
            "Gestion des erreurs robuste",
        ]

        for strength in strengths:
            assert strength in deep_dive_content, f"Missing strength: {strength}"

    def test_identifies_problems(self, deep_dive_content):
        """Test that the review identifies specific problems."""
        problems = [
            "Double Scan des Processus",
            "Précision du CPU sur Premier Appel",
            "Format de Persistance Fragile",
            "Détection WSL Non Testée",
        ]

        for problem in problems:
            assert problem in deep_dive_content, f"Missing problem identification: {problem}"

    # ========================================================================
    # PROBLEM-SPECIFIC TESTS
    # ========================================================================

    def test_double_scan_problem(self, deep_dive_content):
        """Test that the double scan problem is well documented."""
        scan_section = deep_dive_content[
            deep_dive_content.find("Double Scan des Processus") : deep_dive_content.find(
                "Double Scan des Processus"
            )
            + 500
        ]

        assert "psutil.process_iter()" in scan_section, (
            "Should show the redundant process iteration"
        )
        assert "Redondance inutile" in scan_section, "Should explain the redundancy"
        assert "consommation CPU accrue" in scan_section, "Should mention CPU impact"

    def test_cpu_precision_problem(self, deep_dive_content):
        """Test that the CPU precision problem is well documented."""
        cpu_section = deep_dive_content[
            deep_dive_content.find("Précision du CPU sur Premier Appel") : deep_dive_content.find(
                "Précision du CPU sur Premier Appel"
            )
            + 500
        ]

        assert "cpu_percent(interval=0)" in cpu_section, "Should show the problematic CPU call"
        assert "Toujours 0 au premier appel" in cpu_section, "Should explain the issue"
        assert "Métriques CPU imprécises" in cpu_section, "Should mention accuracy impact"

    def test_persistence_problem(self, deep_dive_content):
        """Test that the persistence problem is well documented."""
        persistence_section = deep_dive_content[
            deep_dive_content.find("Format de Persistance Fragile") : deep_dive_content.find(
                "Format de Persistance Fragile"
            )
            + 500
        ]

        assert "rsplit" in persistence_section, "Should show the fragile parsing"
        assert "Risque de corruption des données" in persistence_section, "Should explain the risk"

    def test_wsl_testing_problem(self, deep_dive_content):
        """Test that the WSL testing problem is well documented."""
        wsl_section = deep_dive_content[
            deep_dive_content.find("Détection WSL Non Testée") : deep_dive_content.find(
                "Détection WSL Non Testée"
            )
            + 500
        ]

        assert "Code win32 non testé" in wsl_section, "Should mention untested code"
        assert "Fiabilité inconnue sur Windows" in wsl_section, (
            "Should explain the reliability concern"
        )

    # ========================================================================
    # RECOMMENDATION TESTS
    # ========================================================================

    def test_has_shared_snapshot_recommendation(self, deep_dive_content):
        """Test that shared process snapshot recommendation is provided."""
        assert "Snapshot Partagé des Processus" in deep_dive_content
        assert "list(psutil.process_iter())" in deep_dive_content
        assert "self.desktop_detector.scan(processes)" in deep_dive_content
        assert "self.cli_detector.scan(processes)" in deep_dive_content

    def test_has_cpu_interval_recommendation(self, deep_dive_content):
        """Test that CPU interval recommendation is provided."""
        assert "CPU Percent avec Intervalle Minimal" in deep_dive_content
        assert "cpu_percent(interval=0.1)" in deep_dive_content
        assert "Bloquant 100ms mais précis" in deep_dive_content

    def test_has_robust_persistence_recommendation(self, deep_dive_content):
        """Test that robust persistence recommendation is provided."""
        assert "Persistance Robuste des Offsets" in deep_dive_content
        assert "json.loads" in deep_dive_content
        assert "json.dumps" in deep_dive_content
        assert "offsets.json" in deep_dive_content

    def test_has_windows_testing_recommendation(self, deep_dive_content):
        """Test that Windows testing recommendation is provided."""
        assert "Tests Complets Windows" in deep_dive_content
        assert "@pytest.mark.windows" in deep_dive_content
        assert "test_win32gui_active_window" in deep_dive_content
        assert "test_wsl_process_detection" in deep_dive_content

    # ========================================================================
    # PROCESS DETECTION TESTS
    # ========================================================================

    def test_process_detection_algorithm(self, deep_dive_content):
        """Test that process detection algorithm is analyzed."""
        detection_section = deep_dive_content[
            deep_dive_content.find("Détection des Processus CLI") : deep_dive_content.find(
                "Analyse de l'Historique Shell"
            )
        ]

        assert "_is_ai_process" in detection_section
        assert "_update_metrics" in detection_section
        assert "_on_process_exit" in detection_section
        assert "_active_pids" in detection_section

    def test_process_matching_problems(self, deep_dive_content):
        """Test that process matching problems are identified."""
        detection_section = deep_dive_content[
            deep_dive_content.find("Détection des Processus CLI") : deep_dive_content.find(
                "Analyse de l'Historique Shell"
            )
        ]

        assert "Correspondance des Noms de Processus" in detection_section
        assert "Faux positifs possibles" in detection_section
        assert "ollama" in detection_section
        assert "ollama-server" in detection_section

    def test_memory_consumption_problems(self, deep_dive_content):
        """Test that memory consumption problems are identified."""
        detection_section = deep_dive_content[
            deep_dive_content.find("Détection des Processus CLI") : deep_dive_content.find(
                "Analyse de l'Historique Shell"
            )
        ]

        assert "Consommation Mémoire" in detection_section
        assert "Stocke des données inutiles" in detection_section
        assert "proc.as_dict" in detection_section

    def test_process_cache_problems(self, deep_dive_content):
        """Test that process cache problems are identified."""
        detection_section = deep_dive_content[
            deep_dive_content.find("Détection des Processus CLI") : deep_dive_content.find(
                "Analyse de l'Historique Shell"
            )
        ]

        assert "Pas de Cache des Processus" in detection_section
        assert "Appels système répétitifs" in detection_section

    def test_process_detection_recommendations(self, deep_dive_content):
        """Test that process detection recommendations are provided."""
        assert "Correspondance Exacte des Processus" in deep_dive_content
        assert "Optimisation de la Consommation Mémoire" in deep_dive_content
        assert "Cache des Informations des Processus" in deep_dive_content
        assert "_process_cache" in deep_dive_content

    # ========================================================================
    # SHELL HISTORY TESTS
    # ========================================================================

    def test_shell_format_table(self, deep_dive_content):
        """Test that shell format table is comprehensive."""
        shell_table = deep_dive_content[
            deep_dive_content.find("| Shell | Format | Exemple | Défis |") : deep_dive_content.find(
                "| Shell | Format | Exemple | Défis |"
            )
            + 500
        ]

        assert "zsh" in shell_table
        assert "bash" in shell_table
        assert "PowerShell" in shell_table
        assert "Horodatages en secondes" in shell_table
        assert "Pas d'horodatage" in shell_table
        assert "Parsing JSON requis" in shell_table

    def test_shell_history_problems(self, deep_dive_content):
        """Test that shell history problems are identified."""
        # Find the shell history section specifically
        shell_history_start = deep_dive_content.find("### 3. Analyse de l'Historique Shell")
        wsl_start = deep_dive_content.find("### 4. Détection WSL")
        shell_section = deep_dive_content[shell_history_start:wsl_start]

        assert "Parsing Fragile" in shell_section
        assert "Pas de Validation des Commandes" in shell_section
        assert "Gestion des Encodages" in shell_section
        assert "Caractères de remplacement" in shell_section

    def test_shell_history_recommendations(self, deep_dive_content):
        """Test that shell history recommendations are provided."""
        assert "Parsing Robuste avec Validation" in deep_dive_content
        assert "Validation des Commandes" in deep_dive_content
        assert "Gestion Améliorée des Encodages" in deep_dive_content
        assert "_parse_zsh_line" in deep_dive_content
        assert "_is_valid_command" in deep_dive_content

    # ========================================================================
    # WSL DETECTION TESTS
    # ========================================================================

    def test_wsl_implementation(self, deep_dive_content):
        """Test that WSL implementation is analyzed."""
        wsl_section = deep_dive_content[
            deep_dive_content.find("Détection WSL") : deep_dive_content.find(
                "Tests de Validation Proposés"
            )
        ]

        assert 'platform.system() == "Windows"' in wsl_section
        assert "subprocess.run" in wsl_section
        assert '["wsl", "--list", "--running"]' in wsl_section

    def test_wsl_problems(self, deep_dive_content):
        """Test that WSL problems are identified."""
        wsl_section = deep_dive_content[
            deep_dive_content.find("Détection WSL") : deep_dive_content.find(
                "Tests de Validation Proposés"
            )
        ]

        assert "Configuration Partagée" in wsl_section
        assert "Inadéquat pour les outils Linux" in wsl_section
        assert "Pas de Tests" in wsl_section
        assert "Gestion des Erreurs Limitée" in wsl_section

    def test_wsl_recommendations(self, deep_dive_content):
        """Test that WSL recommendations are provided."""
        assert "Configuration Spécifique Linux" in deep_dive_content
        assert "Tests Complets" in deep_dive_content
        assert "Gestion des Erreurs Robuste" in deep_dive_content
        assert "ai_config.yaml" in deep_dive_content
        assert "linux:" in deep_dive_content
        assert "wsl:" in deep_dive_content

    # ========================================================================
    # TEST VALIDATION TESTS
    # ========================================================================

    def test_process_detection_tests_provided(self, deep_dive_content):
        """Test that process detection tests are proposed."""
        test_section = deep_dive_content[
            deep_dive_content.find("Tests de Validation Proposés") : deep_dive_content.find(
                "Checklist d'Amélioration Priorisée"
            )
        ]

        assert "test_ai_process_detection" in test_section
        assert "test_non_ai_process_ignored" in test_section
        assert "MockProcess" in test_section
        assert "psutil.process_iter" in test_section

    def test_state_tracking_tests_provided(self, deep_dive_content):
        """Test that state tracking tests are proposed."""
        test_section = deep_dive_content[
            deep_dive_content.find("Tests de Validation Proposés") : deep_dive_content.find(
                "Checklist d'Amélioration Priorisée"
            )
        ]

        assert "test_process_lifecycle_tracking" in test_section
        assert "process start/stop" in test_section
        assert "_active_pids" in test_section

    def test_persistence_tests_provided(self, deep_dive_content):
        """Test that persistence tests are proposed."""
        test_section = deep_dive_content[
            deep_dive_content.find("Tests de Validation Proposés") : deep_dive_content.find(
                "Checklist d'Amélioration Priorisée"
            )
        ]

        assert "test_shell_history_offset_persistence" in test_section
        assert "ShellHistoryParser" in test_section
        assert "parse_file" in test_section

    def test_performance_tests_provided(self, deep_dive_content):
        """Test that performance tests are proposed."""
        test_section = deep_dive_content[
            deep_dive_content.find("Tests de Validation Proposés") : deep_dive_content.find(
                "Checklist d'Amélioration Priorisée"
            )
        ]

        assert "test_process_scan_performance" in test_section
        assert "test_memory_usage" in test_section
        assert "tracemalloc" in test_section
        assert "< 0.5" in test_section
        assert "< 20" in test_section

    def test_resilience_tests_provided(self, deep_dive_content):
        """Test that resilience tests are proposed."""
        test_section = deep_dive_content[
            deep_dive_content.find("Tests de Validation Proposés") : deep_dive_content.find(
                "Checklist d'Amélioration Priorisée"
            )
        ]

        assert "test_access_denied_process" in test_section
        assert "test_corrupted_history_file" in test_section
        assert "AccessDenied" in test_section
        assert "Failed to parse" in test_section

    # ========================================================================
    # CHECKLIST AND PRIORITIZATION TESTS
    # ========================================================================

    def test_has_prioritized_checklist(self, deep_dive_content):
        """Test that the review includes a prioritized improvement checklist."""
        checklist_section = deep_dive_content[
            deep_dive_content.find("Checklist d'Amélioration Priorisée") : deep_dive_content.find(
                "Métriques de Qualité Proposées"
            )
        ]

        assert "- [ ] ✅ **Critique**" in checklist_section
        assert "- [ ] ⚠️ **Majeur**" in checklist_section
        assert "- [ ] 📝 **Mineur**" in checklist_section

    def test_checklist_has_specific_items(self, deep_dive_content):
        """Test that checklist has specific improvement items."""
        checklist_section = deep_dive_content[
            deep_dive_content.find("Checklist d'Amélioration Priorisée") : deep_dive_content.find(
                "Métriques de Qualité Proposées"
            )
        ]

        items = [
            "Implémenter le snapshot partagé des processus",
            "Ajouter des tests complets pour Windows",
            "Améliorer la persistance des offsets shell",
            "Optimiser la consommation mémoire des processus",
            "Ajouter la correspondance exacte des processus",
            "Implémenter le parsing robuste de l'historique shell",
            "Ajouter la configuration spécifique Linux pour WSL",
            "Améliorer la gestion des erreurs WSL",
            "Ajouter la validation des commandes shell",
            "Implémenter la gestion améliorée des encodages",
        ]

        for item in items:
            assert item in checklist_section, f"Missing checklist item: {item}"

    # ========================================================================
    # QUALITY METRICS TESTS
    # ========================================================================

    def test_quality_metrics_table(self, deep_dive_content):
        """Test that quality metrics table is comprehensive."""
        metrics_section = deep_dive_content[
            deep_dive_content.find("Métriques de Qualité Proposées") : deep_dive_content.find(
                "Conclusion et Recommandations Finales"
            )
        ]

        assert (
            "| Métrique | Cible Actuelle | Cible Améliorée | Méthode de Mesure |" in metrics_section
        )
        assert "Temps de scan" in metrics_section
        assert "Mémoire max" in metrics_section
        assert "Précision de détection" in metrics_section
        assert "Faux positifs" in metrics_section
        assert "Couverture des shells" in metrics_section
        assert "Temps de parsing historique" in metrics_section

    def test_metrics_have_targets(self, deep_dive_content):
        """Test that metrics have specific targets."""
        metrics_section = deep_dive_content[
            deep_dive_content.find("Métriques de Qualité Proposées") : deep_dive_content.find(
                "Conclusion et Recommandations Finales"
            )
        ]

        assert "< 1s" in metrics_section
        assert "< 0.5s" in metrics_section
        assert "~40MB" in metrics_section
        assert "< 20MB" in metrics_section
        assert "95%" in metrics_section
        assert "98%" in metrics_section
        assert "< 3%" in metrics_section
        assert "< 1%" in metrics_section
        assert "3/3" in metrics_section
        assert "4/4" in metrics_section

    # ========================================================================
    # CONCLUSION AND RECOMMENDATIONS TESTS
    # ========================================================================

    def test_has_conclusion(self, deep_dive_content):
        """Test that the review has a proper conclusion."""
        conclusion_section = deep_dive_content[
            deep_dive_content.find(
                "Conclusion et Recommandations Finales"
            ) : deep_dive_content.find("Annexes")
        ]

        assert "solide et fonctionnelle" in conclusion_section
        assert "améliorations pourraient augmenter" in conclusion_section
        assert "performance" in conclusion_section
        assert "précision" in conclusion_section
        assert "maintenabilité" in conclusion_section

    def test_has_roadmap(self, deep_dive_content):
        """Test that the review includes a recommended roadmap."""
        conclusion_section = deep_dive_content[
            deep_dive_content.find(
                "Conclusion et Recommandations Finales"
            ) : deep_dive_content.find("Annexes")
        ]

        assert "Roadmap Recommandée" in conclusion_section
        assert "Semaine 1" in conclusion_section
        assert "Semaine 2" in conclusion_section
        assert "Semaine 3" in conclusion_section

    def test_roadmap_has_specific_tasks(self, deep_dive_content):
        """Test that roadmap has specific weekly tasks."""
        conclusion_section = deep_dive_content[
            deep_dive_content.find(
                "Conclusion et Recommandations Finales"
            ) : deep_dive_content.find("Annexes")
        ]

        assert "Snapshot partagé + tests Windows" in conclusion_section
        assert "critique pour la fiabilité" in conclusion_section
        assert "Persistance robuste + optimisation mémoire" in conclusion_section
        assert "Parsing amélioré + configuration WSL" in conclusion_section

    # ========================================================================
    # ANNEXES TESTS
    # ========================================================================

    def test_has_implementation_examples(self, deep_dive_content):
        """Test that annexes include implementation examples."""
        annexes_section = deep_dive_content[deep_dive_content.find("Annexes") :]

        assert "Implémentation du Snapshot Partagé" in annexes_section
        assert "Implémentation de la Persistance Robuste" in annexes_section
        assert "Implémentation de la Détection Robuste des Processus" in annexes_section
        assert "class MainDetector:" in annexes_section
        assert "class ShellHistoryParser:" in annexes_section
        assert "class CLIDetector:" in annexes_section

    def test_shared_snapshot_implementation(self, deep_dive_content):
        """Test that shared snapshot implementation is complete."""
        annexes_section = deep_dive_content[
            deep_dive_content.find("Implémentation du Snapshot Partagé") : deep_dive_content.find(
                "Implémentation de la Persistance Robuste"
            )
        ]

        assert "class MainDetector:" in annexes_section
        assert (
            "def __init__(self, config: AppConfig, telemetry: TelemetryManager):" in annexes_section
        )
        assert "self.desktop_detector = DesktopDetector(config, telemetry)" in annexes_section
        assert "self.cli_detector = CLIDetector(config, telemetry)" in annexes_section
        assert "def scan(self):" in annexes_section
        assert "processes = list(psutil.process_iter())" in annexes_section
        assert "self.desktop_detector.scan(processes)" in annexes_section
        assert "self.cli_detector.scan(processes)" in annexes_section

    def test_robust_persistence_implementation(self, deep_dive_content):
        """Test that robust persistence implementation is complete."""
        persistence_section = deep_dive_content[
            deep_dive_content.find(
                "Implémentation de la Persistance Robuste"
            ) : deep_dive_content.find("Implémentation de la Détection Robuste des Processus")
        ]

        assert "class ShellHistoryParser:" in persistence_section
        assert 'self._offset_file = self._state_dir / "offsets.json"' in persistence_section
        assert "def _load_offsets(self) -> dict[str, int]:" in persistence_section
        assert "def _save_offsets(self):" in persistence_section
        assert "json.loads" in persistence_section
        assert "json.dumps" in persistence_section

    def test_robust_process_detection_implementation(self, deep_dive_content):
        """Test that robust process detection implementation is complete."""
        detection_section = deep_dive_content[
            deep_dive_content.find("Implémentation de la Détection Robuste des Processus") :
        ]

        assert "class CLIDetector:" in detection_section
        assert "self._process_cache = {}  # pid -> process_info" in detection_section
        assert (
            "def _get_process_info(self, proc: psutil.Process) -> dict | None:" in detection_section
        )
        assert "def _is_ai_process(self, proc_info: dict) -> bool:" in detection_section
        assert "def scan(self, processes: list | None = None):" in detection_section
        assert "# Correspondance exacte d'abord (plus rapide)" in detection_section
        assert "# Correspondance partielle dans la ligne de commande" in detection_section

    # ========================================================================
    # COMPREHENSIVE VALIDATION TESTS
    # ========================================================================

    def test_recommendations_have_timelines(self, deep_dive_content):
        """Test that recommendations include implementation timelines."""
        assert "Semaine 1" in deep_dive_content, "Should have week 1 timeline"
        assert "Semaine 2" in deep_dive_content, "Should have week 2 timeline"
        assert "Semaine 3" in deep_dive_content, "Should have week 3 timeline"

        # Should mention what to implement each week
        semaine_1_content = deep_dive_content[
            deep_dive_content.find("Semaine 1") : deep_dive_content.find("Semaine 2")
        ]
        assert "Snapshot partagé + tests Windows" in semaine_1_content, (
            "Week 1 should focus on shared snapshot and Windows tests"
        )
        assert "critique pour la fiabilité" in semaine_1_content, (
            "Week 1 should mention reliability"
        )

    def test_has_architectural_decision(self, deep_dive_content):
        """Test that architectural decisions are discussed."""
        conclusion_section = deep_dive_content[
            deep_dive_content.find(
                "Conclusion et Recommandations Finales"
            ) : deep_dive_content.find("Annexes")
        ]

        assert "Décision Architecturale Clé" in conclusion_section
        assert "compromis entre précision" in conclusion_section
        assert "performance" in conclusion_section
        assert "doit être évalué" in conclusion_section

    def test_review_is_comprehensive(self, deep_dive_lines):
        """Test that the review is sufficiently comprehensive."""
        line_count = len(deep_dive_lines)
        assert line_count > 400, f"Review should be comprehensive (>400 lines), got {line_count}"

        # Count key elements
        code_blocks = sum(1 for line in deep_dive_lines if line.strip().startswith("```"))
        assert code_blocks >= 10, f"Should have at least 10 code blocks, got {code_blocks}"

        # Count recommendations
        recommendations = sum(1 for line in deep_dive_lines if "Recommandations" in line)
        assert recommendations >= 5, (
            f"Should have multiple recommendation sections, got {recommendations}"
        )

    def test_review_is_actionable(self, deep_dive_content):
        """Test that the review provides actionable recommendations."""
        # Should have specific implementation guidance
        assert "class MainDetector:" in deep_dive_content
        assert "class ShellHistoryParser:" in deep_dive_content
        assert "class CLIDetector:" in deep_dive_content

        # Should have test examples
        assert "def test_ai_process_detection():" in deep_dive_content
        assert "def test_process_scan_performance():" in deep_dive_content
        assert "def test_corrupted_history_file():" in deep_dive_content

        # Should have specific metrics
        assert "Temps de scan" in deep_dive_content
        assert "Mémoire max" in deep_dive_content
        assert "Précision de détection" in deep_dive_content
