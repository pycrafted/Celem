








// Sélection des éléments
const sidebar = document.querySelector('.sidebare');
const btn = document.getElementById('btn');

// Fonction pour définir l'état dans le localStorage
function toggleSidebar() {
  sidebar.classList.toggle('open'); // Ouvrir/Fermer la barre
  const isOpen = sidebar.classList.contains('open');
  localStorage.setItem('sidebarState', isOpen ? 'open' : 'closed'); // Sauvegarder l'état
}

// Gestionnaire de clic sur le bouton menu
btn.addEventListener('click', toggleSidebar);

// Appliquer l'état sauvegardé au chargement
document.addEventListener('DOMContentLoaded', () => {
  const savedState = localStorage.getItem('sidebarState');
  if (savedState === 'open') {
    sidebar.classList.add('open'); // Garder ouvert
  } else {
    sidebar.classList.remove('open'); // Garder fermé
  }
});
