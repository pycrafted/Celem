import unittest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

class TestLoginPage(unittest.TestCase):
    def setUp(self):
        # Configurer le WebDriver pour Chrome
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        self.driver.maximize_window()
        self.base_url = "http://127.0.0.1:8000/login/"

    def test_successful_login(self):
        # Naviguer vers la page de connexion
        self.driver.get(self.base_url)

        # Trouver les champs de saisie pour le nom d'utilisateur et le mot de passe
        username_field = self.driver.find_element(By.NAME, "username")
        password_field = self.driver.find_element(By.NAME, "password")

        # Entrer les identifiants de test
        username_field.send_keys("testuser")
        password_field.send_keys("testpassword123")

        # Soumettre le formulaire
        password_field.send_keys(Keys.RETURN)

        # Attendre que la page suivante charge
        time.sleep(2)

        # Vérifier que l'utilisateur est redirigé vers la page d'ajout de facture
        self.assertEqual(self.driver.current_url, "http://127.0.0.1:8000/",
                         "La redirection après connexion a échoué")

    def tearDown(self):
        # Fermer le navigateur
        self.driver.quit()

if __name__ == "__main__":
    unittest.main()