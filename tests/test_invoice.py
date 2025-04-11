import os
import sys
import unittest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Ajouter le répertoire racine du projet au PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Configurer Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_invoice.settings")
import django
django.setup()
from fact_app.models import Invoice

class TestInvoiceCreation(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        self.driver.maximize_window()
        self.base_url = "http://127.0.0.1:8000/login/"

        # Se connecter
        self.driver.get(self.base_url)
        username_field = self.driver.find_element(By.NAME, "username")
        password_field = self.driver.find_element(By.NAME, "password")
        username_field.send_keys("lah")
        password_field.send_keys("lah")
        password_field.send_keys(Keys.RETURN)

        # Attendre la redirection vers add-invoice
        WebDriverWait(self.driver, 10).until(
            EC.url_to_be("http://127.0.0.1:8000/")
        )

    def test_create_invoice(self):
        # Aller à la page de création de facture
        self.driver.get("http://127.0.0.1:8000/")

        # Attendre que le formulaire soit chargé
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "customer"))
        )

        # Remplir le nom du client
        self.driver.find_element(By.ID, "customer").send_keys("Client Test")

        # Sélectionner "Test Service" (ID=1) avec JavaScript
        service_select = self.driver.find_element(By.ID, "service-1")
        self.driver.execute_script("arguments[0].value = '1'; arguments[0].dispatchEvent(new Event('change'));", service_select)
        time.sleep(1)  # Attendre que le prix se mette à jour

        # Soumettre le formulaire
        submit_button = self.driver.find_element(By.CLASS_NAME, "boutton-soumission")
        submit_button.click()

        # Diagnostic : Vérifier le nombre de fenêtres
        time.sleep(2)  # Attendre un peu après le clic
        print("Nombre de fenêtres après soumission :", len(self.driver.window_handles))

        # Attendre la redirection vers la page principale
        WebDriverWait(self.driver, 10).until(
            EC.url_to_be("http://127.0.0.1:8000/")
        )

        # Vérifier que la facture a été créée dans la base
        invoice = Invoice.objects.filter(customer="Client Test").first()
        self.assertIsNotNone(invoice, "La facture n'a pas été créée dans la base")
        self.assertEqual(invoice.total, 10000, "Le total de la facture est incorrect")  # 1 * 10000

    def tearDown(self):
        # Nettoyer la base de données
        Invoice.objects.filter(customer="Client Test").delete()
        self.driver.quit()

if __name__ == "__main__":
    unittest.main()