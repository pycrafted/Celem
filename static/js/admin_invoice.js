document.addEventListener('DOMContentLoaded', function() {
    const serviceSelects = document.querySelectorAll('select[name$="-service"]');

    serviceSelects.forEach(function(serviceSelect) {
        serviceSelect.addEventListener('change', function() {
            const serviceId = this.value;
            const prixInput = this.closest('tr').querySelector('input[name$="-prix"]');
            console.log("Service ID sélectionné : ", serviceId);

            if (serviceId) {
                // Effectuer une requête AJAX pour récupérer le prix du service
                fetch(`/get-service-price/${serviceId}/`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error("Erreur dans la requête");
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log("Prix récupéré :", data.prix);
                        prixInput.value = data.prix;  // Mettre à jour le champ prix
                    })
                    .catch(error => {
                        console.error("Erreur lors de la récupération du prix :", error);
                        prixInput.value = '';  // Réinitialiser en cas d'erreur
                    });
            } else {
                prixInput.value = '';  // Réinitialiser si aucun service n'est sélectionné
            }
        });
    });
});
