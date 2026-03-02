#!/usr/bin/env python3
"""
Test unitaire pour le fix quality_rejection - approche TDD
Phase: Write test → Fix code → Validate
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Import des modules à tester
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.terraform_generator import TerraformGenerator
from src.enforcement_validator import EnforcementValidator
from src.diagnostic_analyzer import DiagnosticAnalyzer


class TestTerraformGenerationTDD(unittest.TestCase):
    """Tests TDD - Generate valid .tf files instead of text descriptions."""
    
    def setUp(self):
        """Prépare l'environnement de test - GREEN."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.generator = TerraformGenerator(output_dir=str(self.test_dir))
    
    def tearDown(self):
        """Nettoie l'environnement de test."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_01_creates_actual_tf_file_not_text_description(self):
        """
        TDD Test 1: L'agent doit créer un fichier .tf réel, pas du texte descriptif.
        Ce test DOIT échouer si l'agent génère seulement du texte.
        """
        resources = [
            {
                "type": "aws_instance",
                "name": "web_server",
                "config": {
                    "ami": "ami-0c55b159cbfafe1f0",
                    "instance_type": "t2.micro"
                }
            }
        ]
        
        # Generate actual file
        tf_file = self.generator.create_terraform_file("web_server", resources)
        
        # Verify physical file exists
        self.assertTrue(tf_file.exists(), "Fichier .tf non créé")
        self.assertEqual(tf_file.suffix, ".tf", "L'extension doit être .tf")
        
        # Verify content is not just description text
        content = tf_file.read_text()
        self.assertIn("resource", content, "Le fichier doit contenir 'resource'")
        self.assertIn("aws_instance", content, "Le fichier doit contenir le type de ressource")
        self.assertNotIn("Je vais créer", content, "Le fichier ne doit pas contenir de texte descriptif")
    
    def test_02_enforcement_validator_rejects_text_only_output(self):
        """
        TDD Test 2: Le validateur doit rejeter les sorties textuelles sans code Terraform.
        """
        validator = EnforcementValidator(min_lines_per_file=30)
        
        # Output without any Terraform blocks - should be rejected
        bad_output = "Je vais créer une instance EC2. Voici le code..."
        
        is_valid, errors = validator.validate_output(bad_output)
        
        self.assertFalse(is_valid, "Devrait rejeter le texte sans code Terraform")
        self.assertTrue(len(errors) > 0, "Devrait avoir des erreurs")
    
    def test_03_enforcement_validator_accepts_valid_terraform_code(self):
        """
        TDD Test 3: Le validateur doit accepter les sorties avec du code Terraform valide.
        """
        validator = EnforcementValidator(min_lines_per_file=30)
        
        # Valid Terraform code - should pass
        good_output = '''
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
  count         = 3
  
  tags = {
    Name = "WebServer-${count.index}"
    Environment = "production"
  }
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

output "instance_ids" {
  description = "Instance IDs"
  value       = aws_instance.web[*].id
}
'''
        
        is_valid, errors = validator.validate_output(good_output)
        
        self.assertTrue(is_valid, f"Devrait accepter le code Terraform valide: {errors}")
        self.assertEqual(len(errors), 0, "Ne doit pas avoir d'erreurs")


class TestDiagnosticAnalyzerTDD(unittest.TestCase):
    """Tests TDD - Diagnostic doit détecter le problème."""
    
    def setUp(self):
        self.analyzer = DiagnosticAnalyzer()
    
    def test_04_detects_missing_terraform_files_in_output(self):
        """
        TDD Test 4: Le diagnostic doit détecter si l'output ne contient pas de fichiers Terraform.
        """
        # Descriptive text only - no actual Terraform blocks
        descriptive_output = "Je vais créer une instance EC2 avec un security group. Voici le plan..."
        
        is_valid, message = self.analyzer.analyze_missing_terraform_files(descriptive_output)
        
        self.assertFalse(is_valid, "Devrait détecter que c'est du texte descriptif sans fichiers")
        self.assertIncriptive", message.lower(), "Le("des message doit mentionner 'descriptive'")
    
    def test_05_parses_quality_rejection_error_log(self):
        """
        TDD Test 5: Le diagnostic doit parser les erreurs quality_rejection.
        """
        error_log = "[2025-01-15T10:30:00] Agent Julien Petit output rejected (score 10/10, L1)"
        
        parsed = self.analyzer.parse_log_entry(error_log)
        
        self.assertIsNotNone(parsed, "Devrait parser l'entrée de log")
        self.assertEqual(parsed.get("agent"), "Julien", "Devrait extraire le nom de l'agent")
        self.assertEqual(parsed.get("layer"), 1, "Devrait extraire le layer L1")


class TestNonRegression(unittest.TestCase):
    """Tests de non-régression - Garantir que le fix ne casse pas l'existant."""
    
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.generator = TerraformGenerator(output_dir=str(self.test_dir))
    
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_06_existing_functionality_still_works(self):
        """
        TDD Test 6: Les fonctionnalités existantes doivent continuer à fonctionner.
        """
        # Test basic generation still works
        resources = [{"type": "aws_s3_bucket", "name": "data", "config": {"bucket": "test-bucket"}}]
        
        tf_file = self.generator.create_terraform_file("module_s3", resources)
        
        self.assertTrue(tf_file.exists())
        self.assertIn("aws_s3_bucket", tf_file.read_text())
    
    def test_07_multiple_resources_in_same_file(self):
        """
        TDD Test 7: Plusieurs ressources dans un même fichier doivent fonctionner.
        """
        resources = [
            {"type": "aws_instance", "name": "web", "config": {"ami": "ami-123", "instance_type": "t2.micro"}},
            {"type": "aws_security_group", "name": "web_sg", "config": {"name": "web-sg", "description": "Web SG"}}
        ]
        
        tf_file = self.generator.create_terraform_file("module_multi", resources)
        
        content = tf_file.read_text()
        self.assertIn("aws_instance", content)
        self.assertIn("aws_security_group", content)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)