import unittest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import tempfile

class TestLoginPage(unittest.TestCase):
    def setUp(self):
        # Configurer les options Chrome pour CI
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Mode sans interface graphique
        chrome_options.add_argument("--no-sandbox")  # Nécessaire pour CI
        chrome_options.add_argument("--disable-dev-shm-usage")  # Éviter les problèmes de mémoire partagée
        chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")  # Répertoire utilisateur unique

        # Initialiser le WebDriver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.driver.maximize_window()
        self.base_url = "http://127.0.0.1:8000/login/"

    def test_successful_login(self):
        # Naviguer vers la page de connexion
        self.driver.get(self.base_url)

        # Trouver les champs de saisie
        username_field = self.driver.find_element(By.NAME, "username")
        password_field = self.driver.find_element(By.NAME, "password")

        # Entrer les identifiants
        username_field.send_keys("testuser")
        password_field.send_keys("testpassword123")

        # Soumettre le formulaire
        password_field.send_keys(Keys.RETURN)

        # Attendre la redirection
        time.sleep(20)

        # Vérifier la redirection
        self.assertEqual(self.driver.current_url, "http://127.0.0.1:8000/",
                        "La redirection après connexion a échoué")

    def tearDown(self):
        # Fermer le navigateur
        self.driver.quit()

if __name__ == "__main__":
    unittest.main()